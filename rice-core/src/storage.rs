use super::*;
use fs2::FileExt;
use std::{collections::BTreeMap, fs::OpenOptions, io::Write};
pub fn lock(path: &Path) -> Result<fs::File> {
    fs::create_dir_all(path.parent().context("parent")?)?;
    let f = OpenOptions::new()
        .create(true)
        .read(true)
        .write(true)
        .truncate(false)
        .open(path)?;
    f.lock_exclusive()?;
    Ok(f)
}
pub fn atomic(path: &Path, bytes: &[u8]) -> Result<()> {
    let parent = path.parent().context("parent")?;
    fs::create_dir_all(parent)?;
    let mut f = tempfile::NamedTempFile::new_in(parent)?;
    f.write_all(bytes)?;
    f.as_file().sync_all()?;
    f.persist(path)?;
    fs::File::open(parent)?.sync_all()?;
    Ok(())
}
pub fn write_json(path: &Path, v: &Value) -> Result<()> {
    let mut b = serde_json::to_vec_pretty(v)?;
    b.push(b'\n');
    atomic(path, &b)
}
fn valid(t: &Value) -> bool {
    t.is_object()
        && ["id", "text", "created"]
            .iter()
            .all(|k| t[k].as_str().is_some_and(|s| !s.trim().is_empty()))
        && t["done"].is_boolean()
}
pub fn tasks(a: &[String]) -> Result<Value> {
    let dir = xdg("XDG_DATA_HOME", ".local/share").join("hyprland-rice");
    let _lock = lock(&dir.join(".tasks.lock"))?;
    let path = dir.join("tasks.json");
    let mut data = if path.exists() {
        read(&path).context("Cannot read tasks.json; existing file preserved")?
    } else {
        json!({"version":1,"tasks":[]})
    };
    if data["version"] != 1 || !data["tasks"].is_array() {
        bail!("Invalid task data; existing file preserved");
    }
    let ts = data["tasks"].as_array_mut().unwrap();
    let mut ids = std::collections::HashSet::new();
    if !ts
        .iter()
        .all(|t| valid(t) && ids.insert(t["id"].as_str().unwrap().to_owned()))
    {
        bail!("Invalid task data; existing file preserved");
    }
    let action = a.first().map(String::as_str).unwrap_or("list");
    let p: Value = serde_json::from_str(a.get(1).map(String::as_str).unwrap_or("{}"))?;
    if !p.is_object() {
        bail!("Expected a task object");
    }
    let mut deleted = Value::Null;
    let text = || -> Result<String> {
        let s = p["text"].as_str().context("Write a task first")?.trim();
        if s.is_empty() {
            bail!("Task text cannot be empty");
        }
        Ok(s.into())
    };
    match action {
 "list"=>return Ok(json!({"ok":true,"tasks":ts})),
 "add"=>ts.push(json!({"id":uuid::Uuid::new_v4().to_string(),"text":text()?,"done":false,"created":chrono::Utc::now().to_rfc3339()})),
 "restore"=>{let t=&p["task"];if !valid(t)||ts.iter().any(|v|v["id"]==t["id"]){bail!("Invalid or already restored task");}let i=p["index"].as_i64().unwrap_or(ts.len() as i64).max(0) as usize;ts.insert(i.min(ts.len()),t.clone());},
 "edit"|"toggle"|"delete"=>{let i=ts.iter().position(|t|t["id"]==p["id"]).context("Task no longer exists. Refresh the list.")?; match action {"edit"=>ts[i]["text"]=text()?.into(),"toggle"=>ts[i]["done"]=(!ts[i]["done"].as_bool().unwrap()).into(),_=>deleted=json!({"task":ts.remove(i),"index":i})}},
 _=>bail!("Unknown task action")}
    write_json(&path, &data)?;
    Ok(json!({"ok":true,"tasks":data["tasks"],"deleted":deleted}))
}
pub fn palette(source: &Path, dest: &Path) -> Result<()> {
    let s = read(source)?;
    let color = |k: &str| -> Result<String> {
        let v = s[k]
            .as_str()
            .context("Missing palette role")?
            .trim_start_matches('#');
        if v.len() != 6 || !v.bytes().all(|b| b.is_ascii_hexdigit()) {
            bail!("Invalid palette role: {k}");
        }
        Ok(format!("#{v}"))
    };
    let bg = color("windowBackground")?;
    let fg = color("primaryText")?;
    let muted = color("secondaryText")?;
    let accent = color("accentPrimary")?;
    let mut out = json!({});
    for (keys,value) in [("background surface surfaceDim surfaceBright surfaceContainerLowest surfaceContainerLow surfaceContainer surfaceContainerHigh surfaceContainerHighest surfaceVariant outlineVariant inverseOnSurface onPrimary primaryContainer onSecondary secondaryContainer onTertiary tertiaryContainer",bg),("onBackground onSurface inverseSurface onPrimaryContainer onSecondaryContainer onTertiaryContainer",fg),("onSurfaceVariant outline",muted),("inversePrimary primary secondary tertiary surfaceTint",accent)] {for k in keys.split_whitespace(){out[k]=json!(value);}}
    for (k, v) in [
        ("error", "#ffb4ab"),
        ("onError", "#690005"),
        ("errorContainer", "#93000a"),
        ("onErrorContainer", "#ffdad6"),
    ] {
        out[k] = json!(v);
    }
    if dest.exists() && read(dest).ok().as_ref() == Some(&out) {
        return Ok(());
    }
    write_json(dest, &out)
}
fn pairs(a: &[String]) -> Result<(Vec<(String, String)>, Vec<String>)> {
    let mut pairs = vec![];
    let mut resets = vec![];
    for i in 0..a.len() {
        if a[i] == "--set" {
            pairs.push((
                a.get(i + 1).context("key")?.clone(),
                a.get(i + 2).context("value")?.clone(),
            ));
        }
        if a[i] == "--reset" {
            resets.push(a.get(i + 1).context("reset key")?.clone());
        }
    }
    Ok((pairs, resets))
}
pub fn hypr_config(a: &[String]) -> Result<()> {
    if arg(a, "--anim-preset").is_some() {
        return run(Command::new("bash").arg(config().join("hypr/scripts/Animations.sh")));
    }
    let default = config().join("hyprland-rice/end4/hyprland.conf");
    let path = arg(a, "--file").map(PathBuf::from).unwrap_or(default);
    let _l = lock(&path.with_extension("lock"))?;
    let mut values = BTreeMap::new();
    if path.exists() {
        for line in fs::read_to_string(&path)?.lines() {
            if let Some((k, v)) = line.split_once('=') {
                values.insert(k.trim().to_owned(), v.trim().to_owned());
            }
        }
    }
    let (pairs, resets) = pairs(a)?;
    for k in resets {
        values.remove(&k);
    }
    for (k, v) in pairs {
        if k.is_empty()
            || !k
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"_:-".contains(&b))
            || v.contains(['\n', '\r', '#', '{', '}'])
        {
            bail!("Invalid Hyprland option");
        }
        if v == "[[EMPTY]]" {
            values.remove(&k);
        } else {
            values.insert(k, v);
        }
    }
    let text = values
        .iter()
        .map(|(k, v)| format!("{k} = {v}\n"))
        .collect::<String>();
    atomic(&path, text.as_bytes())?;
    run(Command::new("hyprctl").arg("reload"))
}
pub fn monitor(a: &[String]) -> Result<()> {
    let path = PathBuf::from(arg(a, "--file").context("--file")?);
    let state = path.with_extension("json");
    let _l = lock(&path.with_extension("lock"))?;
    let mut data = if state.exists() {
        read(&state)?
    } else {
        json!({})
    };
    if a.iter().any(|s| s == "--dump-all") {
        println!("{data}");
        return Ok(());
    }
    let name = arg(a, "--output").context("--output")?;
    if name.is_empty()
        || !name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"_.:-".contains(&b))
    {
        bail!("Invalid monitor name");
    }
    if !data.is_object() {
        bail!("Invalid monitor state");
    }
    if data.get(name).is_none() {
        data[name] = json!({});
    }
    let opts = data[name]
        .as_object_mut()
        .context("Invalid monitor options")?;
    let (pairs, resets) = pairs(a)?;
    for k in resets {
        opts.remove(&k);
    }
    for (k, v) in pairs {
        if !"disabled position mode scale transform bitdepth cm sdrbrightness sdrsaturation min_luminance max_luminance max_avg_luminance sdr_min_luminance sdr_max_luminance vrr".split_whitespace().any(|x|x==k)||v.contains(['\n','\r','#','{','}',',']){bail!("Invalid monitor option");}
        opts.insert(k, json!(v));
    }
    if opts.is_empty() {
        data.as_object_mut().unwrap().remove(name);
    }
    let mut text = String::new();
    for (name, o) in data.as_object().unwrap() {
        if o["disabled"] == "1" {
            text += &format!("monitor = {name}, disable\n");
            continue;
        }
        let val = |k: &str, d: &str| o[k].as_str().unwrap_or(d).to_owned();
        text += &format!(
            "monitor = {}, {}, {}, {}",
            name,
            val("mode", "preferred"),
            val("position", "auto"),
            val("scale", "1")
        );
        for (k, v) in o.as_object().context("options")? {
            if !["disabled", "mode", "position", "scale"].contains(&k.as_str()) {
                text += &format!(", {k}, {}", v.as_str().context("value")?);
            }
        }
        text.push('\n');
    }
    write_json(&state, &data)?;
    atomic(&path, text.as_bytes())
}

/// Prune generated thumbnails without traversing personal wallpaper directories.
pub fn prune_thumbnails() -> Result<()> {
    let root = xdg("XDG_CACHE_HOME", ".cache").join("hyprland-rice/end4/thumbnails");
    if !root.exists() {
        return Ok(());
    }
    if root.is_symlink() {
        bail!("Thumbnail cache must not be a symlink");
    }
    let mut files = Vec::new();
    for entry in walkdir::WalkDir::new(&root).follow_links(false) {
        let entry = entry?;
        if entry.file_type().is_file() && entry.path().extension().is_some_and(|e| e == "png") {
            let metadata = entry.metadata()?;
            files.push((
                metadata.modified()?,
                metadata.len(),
                entry.path().to_owned(),
            ));
        }
    }
    files.sort_by_key(|row| row.0);
    let mut bytes: u64 = files.iter().map(|row| row.1).sum();
    let mut count = files.len();
    for (_, size, path) in files {
        if bytes <= 128 * 1024 * 1024 && count <= 512 {
            break;
        }
        fs::remove_file(path)?;
        bytes -= size;
        count -= 1;
    }
    Ok(())
}
