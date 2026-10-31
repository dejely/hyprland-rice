use super::*;
use std::os::unix::fs::symlink;
fn remove(p: &Path) -> Result<()> {
    if p.is_symlink() || p.is_file() {
        fs::remove_file(p)?;
    } else if p.is_dir() {
        fs::remove_dir_all(p)?;
    }
    Ok(())
}
fn restore(e: &Value) -> Result<()> {
    let p = Path::new(e["path"].as_str().context("path")?);
    remove(p)?;
    match e["kind"].as_str() {
        Some("link") => symlink(e["target"].as_str().context("target")?, p)?,
        Some("backup") => {
            let b = Path::new(e["backup"].as_str().context("backup")?);
            if b.is_dir() {
                runtime::copy_tree(b, p)?;
            } else {
                fs::copy(b, p)?;
            }
        }
        _ => {}
    }
    Ok(())
}
fn change(
    p: &Path,
    text: Option<&str>,
    target: Option<&Path>,
    backup: &Path,
    entries: &mut Vec<Value>,
) -> Result<()> {
    let mut e = json!({"path":p,"kind":"missing"});
    if p.is_symlink() {
        e["kind"] = json!("link");
        e["target"] = json!(fs::read_link(p)?);
    } else if p.exists() {
        let b = backup.join(entries.len().to_string());
        if p.is_dir() {
            runtime::copy_tree(p, &b)?;
        } else {
            fs::copy(p, &b)?;
        }
        e["kind"] = json!("backup");
        e["backup"] = json!(b);
    }
    fs::create_dir_all(p.parent().context("parent")?)?;
    entries.push(e);
    let manifest = state().join("end4-profile.json");
    storage::write_json(&manifest, &json!({"entries":entries}))?;
    remove(p)?;
    let e = entries.last_mut().unwrap();
    if let Some(t) = target {
        symlink(t, p)?;
        e["installed_link"] = json!(t);
    } else {
        let text = text.context("content")?;
        storage::atomic(p, text.as_bytes())?;
        e["installed_text"] = json!(text);
    }
    storage::write_json(&manifest, &json!({"entries":entries}))
}
pub fn switch(a: &[String]) -> Result<()> {
    let root = PathBuf::from(a.first().context("checkout")?).canonicalize()?;
    if !matches!(a.get(1).map(String::as_str), Some("install" | "uninstall")) {
        bail!("Usage: install.sh install|uninstall --profile end4-lite|end4|jakoolit [--no-start]");
    }
    let mut i = 2;
    while i < a.len() {
        match a[i].as_str() {
            "--profile" => {
                a.get(i + 1).context("--profile requires a name")?;
                i += 2;
            }
            "--no-start" => i += 1,
            other => bail!("Unknown installer option: {other}"),
        }
    }
    let name = arg(a, "--profile").unwrap_or("end4-lite");
    if !["end4", "end4-lite", "jakoolit"].contains(&name) {
        bail!("Unknown profile");
    }
    let no_start = a.iter().any(|s| s == "--no-start");
    let uninstall = a.iter().any(|s| s == "uninstall");
    fs::create_dir_all(state())?;
    let _l = storage::lock(&state().join("profiles.lock"))?;
    let manifest = state().join("end4-profile.json");
    let stamp = chrono::Utc::now().format("%Y%m%d-%H%M%S-%f").to_string();
    let runtime = state().join("end4-runtimes").join(&stamp);
    if name != "jakoolit" && !uninstall {
        if !config().join("hypr/hyprland.conf").is_file() {
            bail!("Install JaKooLit/Hyprland first");
        }
        // Build before changing an existing profile, so a bad patch leaves it intact.
        runtime::build(&root, &runtime, name == "end4-lite")?;
    }

    if manifest.exists() {
        let old = read(&manifest)?;
        let entries = old["entries"].as_array().context("manifest")?;
        for e in entries {
            let p = Path::new(e["path"].as_str().context("path")?);
            if let Some(s) = e["installed_text"].as_str() {
                if fs::read_to_string(p).ok().as_deref() != Some(s) {
                    bail!("Externally edited profile file preserved: {}", p.display());
                }
            }
            if let Some(s) = e["installed_link"].as_str() {
                if fs::read_link(p).ok().as_deref() != Some(Path::new(s)) {
                    bail!("Externally changed profile link preserved: {}", p.display());
                }
            }
        }
        for e in entries.iter().rev() {
            restore(e)?;
        }
        fs::remove_file(&manifest)?;
    }
    if name == "jakoolit" || uninstall {
        storage::write_json(
            &state().join("profile.json"),
            &json!({"profile":"jakoolit"}),
        )?;
        if !no_start {
            activate("jakoolit")?;
        }
        println!("Profile: jakoolit; tasks and personal settings preserved");
        return Ok(());
    }
    let backup = state().join("backups").join(format!("end4-{stamp}"));
    fs::create_dir_all(&backup)?;
    let settings = config().join("hyprland-rice/end4/config.json");
    if settings.exists() {
        fs::copy(&settings, backup.join("settings.json"))?;
    } else {
        let mut d = read(&root.join("integration/defaults.json"))?;
        d["background"]["wallpaperPath"] = json!(config()
            .join("rofi/.current_wallpaper")
            .canonicalize()
            .context("Cannot find current wallpaper")?);
        storage::write_json(&settings, &d)?;
    }
    storage::palette(
        &config().join("quickshell/qml_color.json"),
        &state().join("end4/user/generated/colors.json"),
    )?;
    let session = runtime.join("session");
    fs::create_dir_all(&session)?;
    for file in ["start.sh", "launch.sh", "lock.sh"] {
        fs::copy(root.join("scripts").join(file), session.join(file))?;
    }
    fs::copy(env::current_exe()?, session.join("rice-core"))?;
    for (file, cmd) in [
        ("control.sh", "control"),
        ("desktop.sh", "desktop"),
        ("key-hints.sh", "shortcuts --yad"),
    ] {
        fs::write(session.join(file),format!("#!/usr/bin/env bash\nexec \"$(dirname -- \"$(realpath -- \"$0\")\")/rice-core\" {cmd} \"$@\"\n"))?;
    }
    let mut entries = vec![];
    let result = (|| -> Result<()> {
        for (p, t) in [
            (config().join("quickshell/rice-desktop"), runtime.clone()),
            (config().join("hypr/UserScripts/rice-desktop"), session),
            (
                config().join("systemd/user/rice-desktop.service"),
                root.join("systemd/rice-desktop.service"),
            ),
        ] {
            change(&p, None, Some(&t), &backup, &mut entries)?;
        }
        let pattern = regex::Regex::new(
            r"\b(?:waybar|swaync|dunst|mako|swww-daemon|hyprpaper|mpvpaper)\b|qs\s+(?:-c|--config)\s+overview",
        )?;
        for relative in [
            "hypr/configs/Startup_Apps.conf",
            "hypr/UserConfigs/Startup_Apps.conf",
        ] {
            let p = config().join(relative);
            if !p.exists() {
                continue;
            }
            let mut text = String::new();
            for line in fs::read_to_string(&p)?.lines() {
                if line.trim_start().starts_with("exec") && pattern.is_match(line) {
                    text += "# rice-end4 disabled: ";
                }
                text += line;
                text.push('\n');
            }
            if relative.contains("UserConfigs") && !text.contains("rice-desktop/start.sh") {
                text +=
                    "\nexec-once = bash \"$HOME/.config/hypr/UserScripts/rice-desktop/start.sh\"\n";
            }
            change(&p, Some(&text), None, &backup, &mut entries)?;
        }
        let p = config().join("hypr/UserConfigs/UserKeybinds.conf");
        let mut text = fs::read_to_string(&p).unwrap_or_default();
        text = text.replace(
            "python3 \"$HOME/.config/hypr/UserScripts/rice-desktop/desktop.py\"",
            "bash \"$HOME/.config/hypr/UserScripts/rice-desktop/desktop.sh\"",
        );
        let keys = fs::read_to_string(root.join("integration/keybinds.conf"))?
            .replace("/usr/bin/python3", "bash")
            .replace("control.py", "control.sh");
        text += "\n# BEGIN rice-end4 shortcuts\n";
        text += &keys;
        text += "# END rice-end4 shortcuts\n";
        change(&p, Some(&text), None, &backup, &mut entries)?;
        let p = config().join("hypr/hypridle.conf");
        if p.exists() {
            let re = regex::Regex::new(r"(?m)^(\s*lock_cmd\s*=).*$")?;
            let text = re
                .replace_all(
                    &fs::read_to_string(&p)?,
                    "1 bash \"$HOME/.config/hypr/UserScripts/rice-desktop/lock.sh\"",
                )
                .into_owned();
            change(&p, Some(&text), None, &backup, &mut entries)?;
        }
        for file in ["hyprland.conf", "monitors.conf"] {
            let p = config().join("hyprland-rice/end4").join(file);
            if !p.exists() {
                storage::atomic(&p, b"# Native dashboard overrides\n")?;
            }
        }
        for(relative,extra)in[("hypr/UserConfigs/01-UserDefaults.conf","\nsource = $HOME/.config/hyprland-rice/end4/hyprland.conf\n"),("hypr/hyprland.conf","\nsource = $HOME/.config/hyprland-rice/end4/monitors.conf\n"),("hypr/UserConfigs/WindowRules.conf","\nlayerrule = match:namespace ^quickshell:.*, blur on\nlayerrule = match:namespace ^quickshell:.*, ignore_alpha 0.2\nwindowrule = match:title ^Desktop Settings$, float on\nwindowrule = match:title ^Desktop Settings$, center on\n")]{let p=config().join(relative);let mut text=fs::read_to_string(&p).unwrap_or_default();text+=extra;change(&p,Some(&text),None,&backup,&mut entries)?;}
        storage::write_json(&state().join("profile.json"), &json!({"profile":name}))?;
        Ok(())
    })();
    if let Err(e) = result {
        for entry in entries.iter().rev() {
            restore(entry)?;
        }
        fs::remove_file(&manifest).ok();
        return Err(e);
    }
    if !no_start {
        activate(name)?;
    }
    println!("Profile: {name}; backups: {}", backup.display());
    Ok(())
}
fn activate(name: &str) -> Result<()> {
    run(Command::new("systemctl").args(["--user", "daemon-reload"]))?;
    run(Command::new("hyprctl").arg("reload"))?;
    if name != "jakoolit" {
        for p in [
            "waybar",
            "swaync",
            "swww-daemon",
            "dunst",
            "mako",
            "hyprpaper",
            "mpvpaper",
        ] {
            Command::new("pkill").args(["-x", p]).status().ok();
        }
        Command::new("qs")
            .args(["-c", "overview", "kill"])
            .output()
            .ok();
    }
    if Command::new("pgrep")
        .args(["-x", "hypridle"])
        .output()?
        .status
        .success()
    {
        Command::new("pkill").args(["-x", "hypridle"]).status().ok();
        Command::new("setsid")
            .args(["-f", "hypridle"])
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .spawn()?;
    }
    run(Command::new("bash").arg(config().join("hypr/UserScripts/rice-desktop/start.sh")))?;
    run(Command::new("systemctl").args(["--user", "restart", "rice-desktop.service"]))?;
    if name == "jakoolit" {
        for args in [
            vec!["swww-daemon", "--format", "xrgb"],
            vec!["swaync"],
            vec!["waybar"],
            vec!["qs", "--no-duplicate", "-c", "overview"],
        ] {
            let existing = Command::new("pgrep")
                .args(["-x", args[0]])
                .output()?
                .status
                .success();
            if !existing || args[0] == "qs" {
                Command::new("setsid")
                    .arg("-f")
                    .args(args)
                    .stdin(std::process::Stdio::null())
                    .stdout(std::process::Stdio::null())
                    .stderr(std::process::Stdio::null())
                    .spawn()?;
            }
        }
    }
    Ok(())
}
