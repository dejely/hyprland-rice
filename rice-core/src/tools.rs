//! A transient UI broker. The main QML process remains the only config writer.
use super::*;
use std::os::unix::fs::OpenOptionsExt;
use std::os::unix::process::CommandExt;
use std::{
    io::{BufRead, BufReader, Write},
    process::Stdio,
    sync::mpsc,
    time::{Duration, Instant},
};
fn changes(before: &Value, after: &Value, path: &mut Vec<String>, out: &mut Vec<Value>) {
    if before == after {
        return;
    }
    if let Some(object) = after.as_object() {
        for (key, value) in object {
            path.push(key.clone());
            changes(&before[key], value, path, out);
            path.pop();
        }
    } else if !path.is_empty() {
        out.push(json!({"path":path,"value":after}));
    }
}
fn emit(value: Value) -> Result<()> {
    println!("{value}");
    std::io::stdout().flush()?;
    Ok(())
}
/// Keep a long-running helper bound to its QML owner, including abrupt exits.
pub fn parent_exec(a: &[String]) -> Result<()> {
    let parent: libc::pid_t = a.first().context("owner PID")?.parse()?;
    if parent <= 1 {
        bail!("Invalid owner PID");
    }
    // Linux preserves PDEATHSIG across this unprivileged exec. Checking the
    // caller-supplied owner closes the race where it exits before we start.
    unsafe {
        if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGTERM) != 0 {
            return Err(std::io::Error::last_os_error().into());
        }
        if libc::getppid() != parent {
            bail!("Helper owner already exited");
        }
    }
    let error = Command::new(a.get(1).context("helper command")?)
        .args(&a[2..])
        .exec();
    Err(error.into())
}
pub fn run_tool(a: &[String]) -> Result<()> {
    let host = PathBuf::from(a.first().context("tool QML path")?);
    let initial = a.get(1).context("tool action")?;
    let payload = a.get(2).map(String::as_str).unwrap_or("");
    let directory = env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .context("XDG_RUNTIME_DIR")?
        .join("hyprland-rice-tools");
    fs::create_dir_all(&directory)?;
    let temporary = tempfile::tempdir_in(&directory)?;
    let settings = temporary.path().join("config.json");
    let status = temporary.path().join("status.json");
    let mut previous = read(&config().join("hyprland-rice/end4/config.json"))?;
    storage::write_json(&settings, &previous)?;
    let logdir = state().join("end4");
    fs::create_dir_all(&logdir)?;
    let log_path = logdir.join("tools.log");
    if fs::metadata(&log_path).is_ok_and(|m| m.len() > 1024 * 1024) {
        fs::rename(&log_path, logdir.join("tools.previous.log"))?;
    }
    let log = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .mode(0o600)
        .open(&log_path)?;
    let mut command = Command::new("qs");
    command
        .args(["-p"])
        .arg(&host)
        .env("RICE_TOOL_HOST", "1")
        .env("RICE_SETTINGS_PATH", &settings)
        .env("RICE_TOOL_STATUS", &status)
        .env("RICE_TOOL_ACTION", initial)
        .env("RICE_TOOL_PAYLOAD", payload)
        .env(
            "RICE_TOOL_MAIN",
            host.parent().context("host directory")?.join("shell.qml"),
        )
        .stdin(Stdio::null())
        .stdout(Stdio::from(log.try_clone()?))
        .stderr(Stdio::from(log));
    let parent = std::process::id() as libc::pid_t;
    // The UI must also exit if the main shell kills this broker during restart.
    unsafe {
        command.pre_exec(move || {
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGTERM) != 0 {
                return Err(std::io::Error::last_os_error());
            }
            if libc::getppid() != parent {
                libc::_exit(125);
            }
            Ok(())
        });
    }
    let mut child = command.spawn()?;
    let (sender, receiver) = mpsc::channel();
    std::thread::spawn(move || {
        for line in BufReader::new(std::io::stdin()).lines() {
            match line {
                Ok(line) => {
                    if sender.send(line).is_err() {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
    });
    let started = Instant::now();
    let mut last_status = Value::Null;
    let mut pending = Vec::new();
    let mut failed = false;
    let mut closed_since: Option<Instant> = None;
    loop {
        while let Ok(line) = receiver.try_recv() {
            if let Ok(value) = serde_json::from_str::<Value>(&line) {
                pending.push(value);
            }
        }
        if let Ok(current) = read(&settings) {
            let mut patch = Vec::new();
            changes(&previous, &current, &mut Vec::new(), &mut patch);
            if !patch.is_empty() {
                emit(json!({"event":"patch","changes":patch}))?;
                previous = current;
            }
        }
        if let Ok(value) = read(&status) {
            if value != last_status {
                emit(json!({"event":"state","state":value}))?;
                last_status = value;
            }
            let delivered = !pending.is_empty();
            for request in pending.drain(..) {
                let action = request["action"].as_str().unwrap_or("close");
                let payload = request["payload"].as_str().unwrap_or("");
                let result = Command::new("qs")
                    .args(["ipc", "-p"])
                    .arg(&host)
                    .args(["call", "tool", "open", action, payload])
                    .output()?;
                if !result.status.success() {
                    eprintln!("Tool command could not be delivered");
                } else {
                    emit(json!({"event":"ack","id":request["id"]}))?;
                }
            }
            if delivered || last_status["open"] == true {
                closed_since = None;
            } else if last_status["started"] == true && closed_since.is_none() {
                closed_since = Some(Instant::now());
            }
            if closed_since.is_some_and(|since| since.elapsed() > Duration::from_millis(350)) {
                child.kill().ok();
                child.wait().ok();
                break;
            }
        }
        if let Some(status) = child.try_wait()? {
            failed = !status.success();
            break;
        }
        if started.elapsed() > Duration::from_secs(20) && !status.exists() {
            child.kill().ok();
            child.wait().ok();
            bail!("Tool UI did not become ready; see tools.log");
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    // Flush the final settings edit before the private copy is removed.
    if let Ok(current) = read(&settings) {
        let mut patch = Vec::new();
        changes(&previous, &current, &mut Vec::new(), &mut patch);
        if !patch.is_empty() {
            emit(json!({"event":"patch","changes":patch}))?;
        }
    }
    if let Err(error) = memory::reclaim() {
        eprintln!("Service cache cleanup skipped: {error}");
    }
    emit(json!({"event":"closed"}))?;
    if failed {
        bail!("Transient UI exited unexpectedly; see tools.log");
    }
    Ok(())
}
