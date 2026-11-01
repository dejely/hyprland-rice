//! One-shot cache reclamation for the shell's own systemd service.
use super::*;
use std::path::Component;

const MIB: u64 = 1024 * 1024;

fn own_service(group: &str) -> Option<PathBuf> {
    let relative = group.strip_prefix('/')?;
    let path = Path::new(relative);
    if path
        .components()
        .any(|part| !matches!(part, Component::Normal(_)))
    {
        return None;
    }
    let name = path.file_name()?.to_str()?;
    let benchmark = name
        .strip_prefix("rice-benchmark-")
        .and_then(|s| s.strip_suffix(".service"))
        .is_some_and(|s| !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit()));
    if name != "rice-desktop.service" && !benchmark {
        return None;
    }
    Some(Path::new("/sys/fs/cgroup").join(path))
}

fn number(path: &Path) -> Result<u64> {
    Ok(fs::read_to_string(path)?.trim().parse()?)
}

pub fn reclaim() -> Result<Value> {
    let groups = fs::read_to_string("/proc/self/cgroup")?;
    let Some(group) = groups.lines().find_map(|line| line.strip_prefix("0::")) else {
        return Ok(json!({"skipped":"cgroup-v2-unavailable"}));
    };
    let Some(directory) = own_service(group) else {
        return Ok(json!({"skipped":"outside-shell-service"}));
    };
    // Never reclaim a parent slice, another service, or an open tool's working
    // set. This is best effort; older kernels and unprivileged setups may deny it.
    let processes = fs::read_to_string(directory.join("cgroup.procs"))?;
    let shells = processes
        .split_whitespace()
        .filter(|pid| {
            fs::read_to_string(format!("/proc/{pid}/comm")).is_ok_and(|name| name.trim() == "qs")
        })
        .count();
    if shells != 1 {
        return Ok(json!({"skipped":"panel-open-or-shell-unavailable"}));
    }
    let before = number(&directory.join("memory.current"))?;
    let swap_before = number(&directory.join("memory.swap.current"))?;
    let total = before.saturating_add(swap_before);
    if total <= 245 * MIB {
        return Ok(json!({"skipped":"within-budget","bytes":total}));
    }
    let stat = fs::read_to_string(directory.join("memory.stat"))?;
    let field = |key: &str| -> u64 {
        stat.lines()
            .find_map(|line| line.strip_prefix(&format!("{key} ")))
            .and_then(|n| n.parse().ok())
            .unwrap_or(0)
    };
    let file_cache = field("file").saturating_sub(field("shmem"));
    let request = total
        .saturating_sub(235 * MIB)
        .min(file_cache.saturating_sub(8 * MIB))
        .min(512 * MIB);
    if request < MIB {
        return Ok(json!({"skipped":"no-excess-file-cache","bytes":total}));
    }
    let started = std::time::Instant::now();
    let result = fs::write(
        directory.join("memory.reclaim"),
        format!("{request} swappiness=0"),
    );
    // EAGAIN means the kernel reclaimed less than requested. Do not loop or
    // increase pressure; report the actual result. Swappiness=0 selects file
    // reclaim for this non-root cgroup, without requesting anonymous swapping.
    if let Err(error) = result {
        if error.raw_os_error() != Some(libc::EAGAIN) {
            return Ok(json!({"skipped":"kernel-denied","reason":error.to_string()}));
        }
    }
    Ok(
        json!({"before":before,"after":number(&directory.join("memory.current"))?,
        "swapBefore":swap_before,"swapAfter":number(&directory.join("memory.swap.current"))?,
        "requested":request,"elapsedMs":started.elapsed().as_millis()}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn excludes_parent_slices_and_unrelated_services() {
        for path in [
            "/",
            "/user.slice",
            "/user.slice/kitty.scope",
            "/other.service",
            "/user.slice/../rice-desktop.service",
            "/rice-benchmark-.service",
            "/rice-benchmark-abc.service",
        ] {
            assert!(own_service(path).is_none(), "{path}");
        }
        assert!(own_service("/user.slice/app.slice/rice-desktop.service").is_some());
        assert!(own_service("/user.slice/app.slice/rice-benchmark-123.service").is_some());
    }
}
