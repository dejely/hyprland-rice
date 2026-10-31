use super::*;
use std::os::unix::fs::{symlink, PermissionsExt};
pub fn copy_tree(from: &Path, to: &Path) -> Result<()> {
    fs::create_dir_all(to)?;
    for e in walkdir::WalkDir::new(from).min_depth(1) {
        let e = e?;
        let rel = e.path().strip_prefix(from)?;
        if rel.components().any(|c| c.as_os_str() == "__pycache__") {
            continue;
        }
        let dest = to.join(rel);
        if e.file_type().is_dir() {
            fs::create_dir_all(&dest)?;
        } else if e.file_type().is_symlink() {
            symlink(fs::read_link(e.path())?, dest)?;
        } else {
            fs::copy(e.path(), dest)?;
        }
    }
    Ok(())
}
pub fn build(root: &Path, dest: &Path, lite: bool) -> Result<()> {
    let root = root.canonicalize()?;
    let dest = if dest.is_absolute() {
        dest.to_owned()
    } else {
        env::current_dir()?.join(dest)
    };
    fs::create_dir_all(dest.parent().context("parent")?)?;
    let dest = dest
        .parent()
        .unwrap()
        .canonicalize()?
        .join(dest.file_name().context("destination")?);
    if dest.starts_with(&root) {
        bail!("Runtime must be outside checkout");
    }
    if dest.exists() {
        if !dest.join(".rice-generated").exists() {
            bail!("Refusing to replace unmanaged directory");
        }
        fs::remove_dir_all(&dest)?;
    }
    copy_tree(&root.join("vendor/end4-pC"), &dest)?;
    run(Command::new("patch")
        .arg("--batch")
        .arg("--fuzz=0")
        .arg("-p1")
        .arg("-d")
        .arg(&dest)
        .arg("-i")
        .arg(root.join("integration/compat.patch")))?;
    fs::write(dest.join(".rice-generated"), "")?;
    if lite {
        run(Command::new("bash").arg(root.join("scripts/build-native.sh")))?;
        copy_tree(&root.join("rice-core/target/native"), &dest.join("native"))?;
        run(Command::new("patch")
            .arg("--batch")
            .arg("--fuzz=0")
            .arg("-p1")
            .arg("-d")
            .arg(&dest)
            .arg("-i")
            .arg(root.join("integration/lite.patch")))?;
    }
    fs::create_dir_all(dest.join("integration"))?;
    fs::copy(
        root.join("integration/thumbnail.sh"),
        dest.join("integration/thumbnail.sh"),
    )?;
    fs::copy(env::current_exe()?, dest.join("integration/rice-core"))?;
    for (file, cmd) in [
        ("tasks.py", "tasks"),
        ("palette.py", "palette"),
        ("host.py", "host"),
        ("hypr_config.py", "hypr-config"),
        ("monitor_config.py", "monitor-config"),
        ("shortcuts.py", "shortcuts"),
        ("wallpaper.py", "wallpaper"),
    ] {
        let p = dest.join("integration").join(file);
        fs::write(
            &p,
            format!("#!/usr/bin/env bash\nexec \"$(dirname -- \"$0\")/rice-core\" {cmd} \"$@\"\n"),
        )?;
        fs::set_permissions(p, fs::Permissions::from_mode(0o755))?;
    }
    fs::write(
        dest.join("integration/switchwall.sh"),
        "#!/usr/bin/env bash\nexec \"$(dirname -- \"$0\")/rice-core\" wallpaper \"$@\"\n",
    )?;
    for (file, cmd) in [
        ("scripts/hyprland/hypridleconfigurator.py", "idle-config"),
        ("scripts/hyprland/monitor_caps.py", "monitor-caps"),
        ("scripts/clipboard/dedupe.py", "clipboard-dedupe"),
        ("scripts/icon-resolve.py", "icons"),
    ] {
        let p = dest.join(file);
        fs::write(
            &p,
            format!(
                "#!/usr/bin/env bash\nexec \"{}\" {cmd} \"$@\"\n",
                dest.join("integration/rice-core").display()
            ),
        )?;
        fs::set_permissions(p, fs::Permissions::from_mode(0o755))?;
    }
    for e in walkdir::WalkDir::new(&dest) {
        let e = e?;
        if e.path().extension().is_some_and(|s| s == "qml") {
            let mut s = fs::read_to_string(e.path())?;
            for prefix in [
                "\"python3\", Quickshell.shellPath(\"integration/",
                "\"/usr/bin/python3\", Quickshell.shellPath(\"integration/",
            ] {
                s = s.replace(prefix, "Quickshell.shellPath(\"integration/");
            }
            s = s.replace("python3 \\\"", "bash \\\"").replace(
                "\"python3\", root.configuratorScriptPath",
                "root.configuratorScriptPath",
            );
            for variable in [
                "root.idleConfiguratorScriptPath",
                "root.capsScriptPath",
                "root.iconResolverPath",
            ] {
                s = s.replace(&format!("\"python3\", {variable}"), variable);
            }
            s = s.replace("\"python3\", \"-I\", `${FileUtils.trimFileProtocol(Directories.scriptPath)}/clipboard/dedupe.py`", "`${FileUtils.trimFileProtocol(Directories.scriptPath)}/clipboard/dedupe.py`");
            s = s.replace(
                "\"--hold\", \"python3\", Quickshell.shellPath(\"integration/host.py\")",
                "\"--hold\", Quickshell.shellPath(\"integration/host.py\")",
            );
            fs::write(e.path(), s)?;
        }
    }

    println!("{}", dest.display());
    Ok(())
}
pub fn wallpaper(a: &[String]) -> Result<()> {
    let dir = state().join("end4");
    let _l = storage::lock(&dir.join("wallpaper.lock"))?;
    let data = read(&config().join("hyprland-rice/end4/config.json"))?;
    let p = arg(a, "--image")
        .or_else(|| {
            a.first()
                .filter(|s| !s.starts_with('-'))
                .map(String::as_str)
        })
        .or_else(|| data["background"]["wallpaperPath"].as_str())
        .context("wallpaper")?;
    let image = Path::new(p).canonicalize()?;
    run(Command::new("bash")
        .arg(config().join("hypr/scripts/WallustSwww.sh"))
        .arg(&image))?;
    storage::palette(
        &config().join("quickshell/qml_color.json"),
        &dir.join("user/generated/colors.json"),
    )?;
    run(Command::new("qs")
        .args(["ipc", "-c", "rice-desktop", "call", "desktop", "wallpaper"])
        .arg(image))
}
pub fn host(action: &str) -> Result<()> {
    let os = fs::read_to_string("/etc/os-release")?;
    let id = os
        .lines()
        .find_map(|l| l.strip_prefix("ID="))
        .unwrap_or("")
        .trim_matches('"');
    let pm = match id {
        "fedora" | "rhel" | "centos" => "dnf",
        "arch" | "endeavouros" | "cachyos" => "pacman",
        "debian" | "ubuntu" => "apt-get",
        _ => bail!("Unsupported host: {id}"),
    };
    if action == "available" {
        return run(Command::new("sh").args(["-c", "command -v \"$1\" >/dev/null", "sh", pm]));
    }
    if action == "update" {
        return run(Command::new("sudo").arg(pm).args(match pm {
            "dnf" => vec!["upgrade", "--refresh"],
            "pacman" => vec!["-Syu"],
            _ => vec!["upgrade"],
        }));
    }
    let args = match (action, pm) {
        ("count", "dnf") => vec!["rpm", "-qa"],
        ("count", "pacman") => vec!["pacman", "-Qq"],
        ("count", _) => vec!["dpkg-query", "-W"],
        ("check", "dnf") => vec!["dnf", "-q", "check-upgrade"],
        ("check", "pacman") => vec!["checkupdates"],
        ("check", _) => vec!["apt", "list", "--upgradable"],
        _ => bail!("Invalid action"),
    };
    let o = Command::new(args[0]).args(&args[1..]).output()?;
    if ![Some(0), Some(2), Some(100)].contains(&o.status.code()) {
        bail!("Package query failed");
    }
    let text = String::from_utf8(o.stdout)?;
    let n = text
        .lines()
        .filter(|l| !l.trim().is_empty() && !l.starts_with("Listing"))
        .count();
    if action == "count" {
        println!("{n} {pm}");
    } else {
        println!("{n}");
    }
    Ok(())
}
pub fn shortcuts(yad: bool) -> Result<()> {
    let rows: Value =
        serde_json::from_str(&output(Command::new("hyprctl").args(["binds", "-j"]))?)?;
    let mut binds = vec![];
    let mut cmd = Command::new("yad");
    cmd.args([
        "--list",
        "--title=Effective desktop shortcuts",
        "--width=900",
        "--height=700",
        "--column=Shortcut",
        "--column=Action",
    ]);
    for r in rows.as_array().context("bindings")? {
        let mask = r["modmask"].as_u64().unwrap_or(0);
        let mods: Vec<&str> = [(64, "SUPER"), (4, "CTRL"), (8, "ALT"), (1, "SHIFT")]
            .iter()
            .filter(|(bit, _)| mask & bit != 0)
            .map(|(_, name)| *name)
            .collect();
        let key = r["key"]
            .as_str()
            .filter(|s| !s.is_empty())
            .map(str::to_owned)
            .unwrap_or_else(|| format!("code:{}", r["keycode"]));
        let comment = r["description"]
            .as_str()
            .filter(|s| !s.is_empty())
            .map(str::to_owned)
            .unwrap_or_else(|| {
                format!(
                    "{} {}",
                    r["dispatcher"].as_str().unwrap_or(""),
                    r["arg"].as_str().unwrap_or("")
                )
            });
        cmd.arg(format!("{} + {key}", mods.join(" + ")))
            .arg(&comment);
        binds.push(json!({"mods":mods,"key":key,"dispatcher":r["dispatcher"],"params":r["arg"],"comment":comment}));
    }
    if yad {
        run(&mut cmd)
    } else {
        println!(
            "{}",
            json!({"name":"Effective shortcuts","children":[],"keybinds":binds})
        );
        Ok(())
    }
}
pub fn control(action: &str) -> Result<()> {
    if action == "desktop" {
        return desktop();
    }
    if action == "refresh" {
        return run(Command::new("systemctl").args(["--user", "restart", "rice-desktop.service"]));
    }
    let (t, m) = match action {
        "launcher" => ("search", "toggle"),
        "overview" => ("search", "workspacesToggle"),
        "wallpaper" => ("wallpaperSelector", "toggle"),
        "colors" => ("desktop", "colors"),
        "settings" => ("settings", "toggle"),
        "bar-style" => ("desktop", "barStyle"),
        "bar-layout" => ("desktop", "barLayout"),
        "bar-toggle" => ("bar", "toggle"),
        "clipboard" => ("search", "clipboardToggle"),
        "notifications" => ("sidebarRight", "toggle"),
        "help" => ("search", "help"),
        "emoji" => ("search", "emojiToggle"),
        "random-wallpaper" => ("wallpaperSelector", "random"),
        _ => bail!("Unknown action"),
    };
    run(Command::new("qs").args(["ipc", "-c", "rice-desktop", "call", t, m]))
}
pub fn desktop() -> Result<()> {
    let dir = env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .context("XDG_RUNTIME_DIR")?;
    let _l = storage::lock(&dir.join("rice-desktop-toggle.lock"))?;
    let monitors: Value =
        serde_json::from_str(&output(Command::new("hyprctl").args(["monitors", "-j"]))?)?;
    let m = monitors
        .as_array()
        .context("monitors")?
        .iter()
        .find(|m| m["focused"] == true)
        .context("focused monitor")?;
    let name = m["name"].as_str().context("monitor name")?;
    let desktop = format!("rice-desktop-{name}");
    let p = dir.join("rice-desktop-workspaces.json");
    let mut saved = read(&p).unwrap_or(json!({}));
    let target = if m["activeWorkspace"]["name"] == desktop {
        saved[name].as_str().unwrap_or("1").to_owned()
    } else {
        let w = &m["activeWorkspace"];
        saved[name] = json!(if w["id"].as_i64().unwrap_or(0) > 0 {
            w["id"].to_string()
        } else {
            format!("name:{}", w["name"].as_str().context("workspace")?)
        });
        storage::write_json(&p, &saved)?;
        format!("name:{desktop}")
    };
    run(Command::new("hyprctl").args(["dispatch", "workspace", &target]))
}
