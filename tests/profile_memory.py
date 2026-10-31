#!/usr/bin/env python3
"""Isolated native shell memory measurements; never switches the active profile."""
import argparse, json, os, subprocess as sp, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integration'))
from build import build
from palette import atomic_json, sync
p=argparse.ArgumentParser(); p.add_argument('--profile',choices=['end4','end4-lite'],default='end4');p.add_argument('--seconds',type=int,default=600);p.add_argument('--cycles',type=int,default=0);p.add_argument('--render-loop',default='threaded');p.add_argument('--massif',action='store_true');p.add_argument('--omit',default='');p.add_argument('--report',required=True);a=p.parse_args()
def command(*args): return sp.check_output(args,text=True).strip()
original=next(m['name'] for m in json.loads(command('hyprctl','monitors','-j')) if m['focused'])
before={m['name'] for m in json.loads(command('hyprctl','monitors','-j'))}
output=None;unit='rice-benchmark-'+str(os.getpid()); report={'profile':a.profile,'samples':[],'cycles':[]}
with tempfile.TemporaryDirectory(prefix='rice-memory-') as td:
 root=Path(td);runtime=root/'shell'
 try:
  if a.profile=='end4': build(runtime)
  else: sp.run([str(ROOT/'rice-core/target/release/rice-core'),'build',str(ROOT),str(runtime),'end4-lite'],check=True,stdout=sp.DEVNULL)
  data=json.loads((ROOT/'integration/defaults.json').read_text());data['background']['wallpaperPath']=str((Path.home()/'.config/rofi/.current_wallpaper').resolve());data['wallpaperSelector']={'userPath':str(root/'wallpapers')};(root/'wallpapers').mkdir()
  
  for key in a.omit.split(','):
   if key in data['background']['widgets']:data['background']['widgets'][key]['enable']=False
  atomic_json(root/'config/hyprland-rice/end4/config.json',data)
  colors=root/'config/quickshell/qml_color.json';atomic_json(colors,dict(windowBackground='#10151c',primaryText='#eeeeee',secondaryText='#aaaaaa',accentPrimary='#aabbcc'));sync(colors,root/'state/hyprland-rice/end4/user/generated/colors.json')
  sp.run(['hyprctl','output','create','headless'],check=True,stdout=sp.DEVNULL)
  output=next(m['name'] for m in json.loads(command('hyprctl','monitors','-j')) if m['name'] not in before)
  sp.run(['hyprctl','keyword','monitor',output+',1920x1200@60,auto,1'],check=True,stdout=sp.DEVNULL)
  deps=Path.home()/'.local/share/hyprland-rice/deps/usr/lib64'
  env=dict(os.environ,QT_QPA_PLATFORM='wayland',QML_IMPORT_PATH=str(deps/'qt6/qml'),LD_LIBRARY_PATH=str(deps),XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'data'),XDG_STATE_HOME=str(root/'state'),XDG_CACHE_HOME=str(root/'cache'),RICE_TEST_OUTPUT=output,QSG_INFO='1',QSG_RENDER_LOOP=a.render_loop,MALLOC_ARENA_MAX='2',MALLOC_TRIM_THRESHOLD_='131072')
  sp.run(['systemd-run','--user','--quiet','--unit='+unit,'--property=MemoryAccounting=yes','--property=StandardOutput=append:'+str(root/'shell.log'),'--property=StandardError=append:'+str(root/'shell.log'),'env',*[k+'='+v for k,v in env.items() if k in ('HOME','PATH','WAYLAND_DISPLAY','HYPRLAND_INSTANCE_SIGNATURE','XDG_RUNTIME_DIR','XDG_CURRENT_DESKTOP','QT_QPA_PLATFORM','QML_IMPORT_PATH','LD_LIBRARY_PATH','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','RICE_TEST_OUTPUT','QSG_INFO','QSG_RENDER_LOOP','MALLOC_ARENA_MAX','MALLOC_TRIM_THRESHOLD_')],'dbus-run-session',*(['valgrind','--tool=massif','--massif-out-file='+a.report+'.massif','--max-snapshots=30'] if a.massif else []),'qs','-p',str(runtime)],check=True)
  def ipc(target,method,*args):return sp.check_output(['qs','ipc','-p',str(runtime),'call',target,method,*args],env=env,text=True,stderr=sp.DEVNULL).strip()
  for _ in range(600):
   try: json.loads(ipc('desktop','status'));break
   except (sp.CalledProcessError,ValueError):time.sleep(.1)
  else: raise RuntimeError((root/'shell.log').read_text())
  def sample(label):
   props=dict(l.split('=',1) for l in command('systemctl','--user','show',unit,'-p','MemoryCurrent','-p','MemoryPeak','-p','ControlGroup','-p','MemorySwapCurrent','-p','CPUUsageNSec').splitlines())
   cgroup=Path('/sys/fs/cgroup')/props['ControlGroup'].lstrip('/');pids=[int(pid) for f in cgroup.rglob('cgroup.procs') for pid in f.read_text().split()]
   pss=0;rss=0;processes=[]
   for pid in set(pids):
    try:
     sm=dict((l.split(':',1)[0],int(l.split()[1])) for l in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines()[1:] if ':' in l)
     pss+=sm.get('Pss',0);rss+=sm.get('Rss',0);processes.append(dict(name=Path(f'/proc/{pid}/comm').read_text().strip(),pss_kib=sm.get('Pss',0),anon_kib=sm.get('Pss_Anon',0),file_kib=sm.get('Pss_File',0)))
     if Path(f'/proc/{pid}/comm').read_text().strip()=='qs':Path(a.report+'.smaps').write_text(Path(f'/proc/{pid}/smaps').read_text())
    except (OSError,ValueError):pass
   row=dict(label=label,elapsed=round(time.monotonic()-start,1),pss_kib=pss,rss_kib=rss,service_bytes=int(props['MemoryCurrent']),peak_bytes=int(props['MemoryPeak']),swap_bytes=int(props.get('MemorySwapCurrent','0')),cpu_ns=int(props.get('CPUUsageNSec','0')),memory_stat=dict(line.split() for line in (cgroup/'memory.stat').read_text().splitlines()),processes=processes);report['samples'].append(row);Path(a.report).write_text(json.dumps(report,indent=2));print(json.dumps(row),flush=True);return row
  start=time.monotonic();sample('startup')
  while time.monotonic()-start<a.seconds:
   time.sleep(min(30,max(.1,a.seconds-(time.monotonic()-start))));sample('idle')
  for target,method in [('search','toggle'),('search','workspacesToggle'),('search','clipboardToggle'),('wallpaperSelector','toggle'),('settings','toggle'),('sidebarRight','toggle')]:
   for i in range(a.cycles):
    ipc(target,method);time.sleep(.8);ipc(target,method);time.sleep(.4)
    if (i+1)%5==0:sample(target+':'+method+':'+str(i+1))
   if a.cycles:sample(target+':'+method)
  time.sleep(5);sample('settled')
  sp.run(['hyprctl','dispatch','focusmonitor',output],stdout=sp.DEVNULL);time.sleep(1)
  sp.run(['grim','-o',output,a.report+'.png'],check=True)
  Path(a.report+'.log').write_text((root/'shell.log').read_text(errors='replace'))
 finally:
  sp.run(['systemctl','--user','stop',unit],stdout=sp.DEVNULL,stderr=sp.DEVNULL)
  sp.run(['hyprctl','dispatch','focusmonitor',original],stdout=sp.DEVNULL)
  if output:sp.run(['hyprctl','output','remove',output],stdout=sp.DEVNULL)
