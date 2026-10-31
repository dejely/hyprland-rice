use super::*;
pub fn idle(a: &[String]) -> Result<()> {
    let path = PathBuf::from(arg(a, "--file").context("--file")?);
    let _l = storage::lock(&path.with_extension("rice.lock"))?;
    let text = fs::read_to_string(&path)?;
    let re = regex::Regex::new(r"(?ms)^\s*listener\s*\{[^{}]*\}")?;
    let specs = [
        (
            "--lock",
            "loginctl lock-session",
            "loginctl lock-session",
            None,
        ),
        (
            "--screen-off",
            "dpms",
            "hyprctl dispatch dpms off",
            Some("hyprctl dispatch dpms on"),
        ),
        ("--suspend", "$suspend_cmd", "$suspend_cmd", None),
    ];
    let mut result = text.clone();
    for (flag, needle, timeout, resume) in specs {
        if let Some(value) = arg(a, flag) {
            let secs: i64 = value.parse()?;
            let mut replacement = String::new();
            if secs > 0 {
                replacement =
                    format!("listener {{\n    timeout = {secs}\n    on-timeout = {timeout}\n");
                if let Some(r) = resume {
                    replacement += &format!("    on-resume = {r}\n");
                }
                replacement += "}\n";
            }
            let mut found = false;
            result = re
                .replace_all(&result, |caps: &regex::Captures| {
                    if caps[0].contains(needle) {
                        found = true;
                        replacement.clone()
                    } else {
                        caps[0].into()
                    }
                })
                .into_owned();
            if !found {
                result.push('\n');
                result += &replacement;
            }
        }
    }
    // Retain the installed lock command, unrelated listeners and user comments.
    storage::atomic(&path, result.as_bytes())
}
pub fn dedupe(a: &[String]) -> Result<()> {
    use std::io::Write;
    let groups: Vec<Vec<Value>> = serde_json::from_str(a.first().context("groups")?)?;
    let mut doomed = vec![];
    for group in groups {
        let mut seen = std::collections::HashSet::new();
        for id in group {
            let id = id.as_str().map(str::to_owned).unwrap_or(id.to_string());
            if !id.bytes().all(|b| b.is_ascii_digit()) {
                continue;
            }
            let out = Command::new("cliphist").args(["decode", &id]).output()?;
            if !out.status.success() {
                continue;
            }
            let mut bytes = out.stdout;
            while bytes.first().is_some_and(u8::is_ascii_whitespace) {
                bytes.remove(0);
            }
            while bytes.last().is_some_and(u8::is_ascii_whitespace) {
                bytes.pop();
            }
            if !seen.insert(bytes) {
                doomed.push(id);
            }
        }
    }
    if !doomed.is_empty() {
        let mut child = Command::new("cliphist")
            .arg("delete")
            .stdin(std::process::Stdio::piped())
            .spawn()?;
        child
            .stdin
            .take()
            .unwrap()
            .write_all((doomed.join("\n") + "\n").as_bytes())?;
        if !child.wait()?.success() {
            bail!("Clipboard delete failed");
        }
    }
    println!("{}", doomed.len());
    Ok(())
}
fn cta(data: &[u8], start: usize, end: usize) -> (bool, bool) {
    let (mut h, mut d) = (false, false);
    let mut i = start;
    while i < end.min(data.len()) {
        let tag = data[i] >> 5;
        let len = (data[i] & 31) as usize;
        if i + 1 + len > end.min(data.len()) {
            break;
        }
        if tag == 7 && len > 0 {
            h |= data[i + 1] == 6;
            d |= data[i + 1] == 20;
        }
        i += 1 + len;
    }
    (h, d)
}
pub fn caps(a: &[String]) -> Result<()> {
    let mut result = json!({});
    for name in a {
        let path = fs::read_dir("/sys/class/drm")?
            .filter_map(|e| e.ok())
            .find(|e| {
                e.file_name()
                    .to_string_lossy()
                    .ends_with(&format!("-{name}"))
            })
            .map(|e| e.path().join("edid"));
        let bytes = path
            .as_ref()
            .and_then(|p| fs::read(p).ok())
            .unwrap_or_default();
        let mut cap =
            json!({"digital":null,"maxBpc":null,"hdr":null,"hdrDynamic":null,"source":"no-edid"});
        if bytes.len() >= 128 {
            let digital = bytes[20] & 128 != 0;
            let code = (bytes[20] >> 4) & 7;
            let (mut hdr, mut dynamic) = (false, false);
            for ext in bytes[128..].chunks(128) {
                if ext.len() < 5 {
                    continue;
                }
                let (h, d) = match ext[0] {
                    2 => cta(ext, 4, if ext[2] == 0 { 4 } else { ext[2] as usize }),
                    0x70 => {
                        let mut pos = 5;
                        let end = (5 + ext[2] as usize).min(ext.len());
                        let (mut h, mut d) = (false, false);
                        while pos + 3 <= end {
                            let len = ext[pos + 2] as usize;
                            if pos + 3 + len > end {
                                break;
                            }
                            if ext[pos] == 0x81 {
                                let (x, y) = cta(ext, pos + 3, pos + 3 + len);
                                h |= x;
                                d |= y;
                            }
                            pos += 3 + len;
                        }
                        (h, d)
                    }
                    _ => (false, false),
                };
                hdr |= h;
                dynamic |= d;
            }
            cap = json!({"digital":digital,"maxBpc":if digital && (1..=6).contains(&code){Some(4+2*code)}else{None},"hdr":hdr,"hdrDynamic":dynamic,"source":path});
            if bytes.len() < 128 * (1 + bytes[126] as usize) {
                if !hdr {
                    cap["hdr"] = Value::Null;
                }
                if !dynamic {
                    cap["hdrDynamic"] = Value::Null;
                }
            }
        }
        result[name] = cap;
    }
    println!("{result}");
    Ok(())
}
pub fn icons(a: &[String]) -> Result<()> {
    let theme = a.first().context("theme")?;
    if theme.contains('/') || theme == ".." {
        bail!("Invalid theme");
    }
    let dirs = [
        home().join(".icons"),
        xdg("XDG_DATA_HOME", ".local/share").join("icons"),
        PathBuf::from("/usr/share/icons"),
    ];
    let mut result = json!({});
    for name in a.iter().skip(1) {
        if name.contains('/') {
            continue;
        }
        let mut found = None;
        for root in &dirs {
            for t in [theme.as_str(), "hicolor"] {
                let base = root.join(t);
                if !base.exists() {
                    continue;
                }
                for e in walkdir::WalkDir::new(base)
                    .follow_links(true)
                    .into_iter()
                    .filter_map(|e| e.ok())
                {
                    if e.file_type().is_file()
                        && e.path().file_stem().is_some_and(|s| s == name.as_str())
                        && e.path()
                            .extension()
                            .is_some_and(|s| ["svg", "png", "xpm"].iter().any(|x| s == *x))
                    {
                        found = Some(e.path().to_string_lossy().to_string());
                        break;
                    }
                }
                if found.is_some() {
                    break;
                }
            }
            if found.is_some() {
                break;
            }
        }
        result[name] = json!(found.unwrap_or_default());
    }
    println!("{result}");
    Ok(())
}
