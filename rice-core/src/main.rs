use anyhow::{bail, Context, Result};
use serde_json::{json, Value};
use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
};
mod extras;
mod profile;
mod runtime;
mod storage;
mod tools;
fn home() -> PathBuf {
    PathBuf::from(env::var_os("HOME").expect("HOME"))
}
fn xdg(key: &str, fallback: &str) -> PathBuf {
    env::var_os(key)
        .map(PathBuf::from)
        .unwrap_or_else(|| home().join(fallback))
}
fn config() -> PathBuf {
    xdg("XDG_CONFIG_HOME", ".config")
}
fn state() -> PathBuf {
    xdg("XDG_STATE_HOME", ".local/state").join("hyprland-rice")
}
fn output(cmd: &mut Command) -> Result<String> {
    let o = cmd.output()?;
    if !o.status.success() {
        bail!("{}", String::from_utf8_lossy(&o.stderr));
    }
    Ok(String::from_utf8(o.stdout)?)
}
fn run(cmd: &mut Command) -> Result<()> {
    if !cmd.status()?.success() {
        bail!("Command failed: {:?}", cmd);
    }
    Ok(())
}
fn read(path: &Path) -> Result<Value> {
    Ok(serde_json::from_slice(&fs::read(path)?)?)
}
fn arg<'a>(args: &'a [String], key: &str) -> Option<&'a str> {
    args.iter()
        .position(|a| a == key)
        .and_then(|i| args.get(i + 1))
        .map(String::as_str)
}
fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let result = dispatch(&args);
    if let Err(e) = result {
        if args.first().map(String::as_str) == Some("tasks") {
            println!("{}", json!({"ok":false,"error":e.to_string()}));
        } else {
            eprintln!("{e:#}");
        }
        std::process::exit(1);
    }
}
fn dispatch(a: &[String]) -> Result<()> {
    let (cmd, a) = a.split_first().context("Usage: rice-core COMMAND ...")?;
    match cmd.as_str() {
        "idle-config" => extras::idle(a)?,
        "clipboard-dedupe" => extras::dedupe(a)?,
        "monitor-caps" => extras::caps(a)?,
        "icons" => extras::icons(a)?,
        "icon-theme" => extras::icon_theme(a)?,
        "tool" => tools::run_tool(a)?,
        "tasks" => println!("{}", storage::tasks(a)?),
        "cache-prune" => storage::prune_thumbnails()?,
        "palette" => storage::palette(
            Path::new(a.first().context("source")?),
            Path::new(a.get(1).context("destination")?),
        )?,
        "build" => runtime::build(
            Path::new(a.first().context("checkout")?),
            Path::new(a.get(1).context("destination")?),
            a.get(2).map(String::as_str) == Some("end4-lite"),
        )?,
        "profile" => profile::switch(a)?,
        "hypr-config" => storage::hypr_config(a)?,
        "monitor-config" => storage::monitor(a)?,
        "wallpaper" => runtime::wallpaper(a)?,
        "host" => runtime::host(a.first().context("action")?)?,
        "shortcuts" => runtime::shortcuts(a.iter().any(|a| a == "--yad"))?,
        "control" => runtime::control(a.first().context("action")?)?,
        "desktop" => runtime::desktop()?,
        _ => bail!("Unknown command: {cmd}"),
    }
    Ok(())
}
