"""Exercise native CLI contracts against isolated persistent files."""
import concurrent.futures, json, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/'rice-core/target/release/rice-core'
class NativeCore(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.env=dict(os.environ,XDG_DATA_HOME=str(self.root/'data'),XDG_STATE_HOME=str(self.root/'state'),XDG_CONFIG_HOME=str(self.root/'config'))
 def tearDown(self):self.tmp.cleanup()
 def call(self,*args,ok=True):
  r=subprocess.run([str(BIN),*args],env=self.env,capture_output=True,text=True)
  if ok:self.assertEqual(r.returncode,0,r.stderr+r.stdout)
  else:self.assertNotEqual(r.returncode,0)
  return r
 def task(self,action,payload=None,ok=True):return json.loads(self.call('tasks',action,json.dumps(payload or {}),ok=ok).stdout)
 def test_task_lifecycle_and_undo(self):
  t=self.task('add',{'text':' banana '})['tasks'][0];self.assertEqual(t['text'],'banana')
  self.assertEqual(self.task('edit',{'id':t['id'],'text':'changed'})['tasks'][0]['id'],t['id'])
  self.assertTrue(self.task('toggle',{'id':t['id']})['tasks'][0]['done'])
  deleted=self.task('delete',{'id':t['id']})['deleted'];restored=self.task('restore',deleted)['tasks'][0];self.assertEqual(restored['id'],t['id']);self.assertTrue(restored['done'])
  self.assertEqual(self.task('list')['tasks'],[restored])
 def test_concurrent_saves(self):
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda i:self.task('add',{'text':str(i)}),range(40)))
  ts=self.task('list')['tasks'];self.assertEqual(len(ts),40);self.assertEqual(len({t['id'] for t in ts}),40)
 def test_corruption_is_preserved(self):
  self.task('add',{'text':'keep'});p=self.root/'data/hyprland-rice/tasks.json';p.write_text('{invalid');self.task('add',{'text':'bad'},ok=False);self.assertEqual(p.read_text(),'{invalid')
 def test_reject_duplicate_restore_and_empty_edit(self):
  t=self.task('add',{'text':'keep'})['tasks'][0];self.task('restore',{'task':t},ok=False);self.task('edit',{'id':t['id'],'text':' '},ok=False);self.assertEqual(self.task('list')['tasks'][0]['text'],'keep')
 def test_palette_retains_last_valid(self):
  src=self.root/'palette.json';dest=self.root/'colors.json';src.write_text(json.dumps(dict(windowBackground='#10151c',primaryText='#eeeeee',secondaryText='#aaaaaa',accentPrimary='##aabbcc')));self.call('palette',str(src),str(dest));before=dest.read_bytes();src.write_text('{}');self.call('palette',str(src),str(dest),ok=False);self.assertEqual(dest.read_bytes(),before)
 def test_idle_preserves_lock_and_unrelated_listeners(self):
  p=self.root/'idle.conf';p.write_text('general {\n lock_cmd = custom-lock\n}\nlistener {\n timeout = 10\n on-timeout = custom-action\n}\nlistener {\n timeout = 30\n on-timeout = loginctl lock-session\n}\n');self.call('idle-config','--file',str(p),'--lock','60');s=p.read_text();self.assertIn('custom-lock',s);self.assertIn('custom-action',s);self.assertIn('timeout = 60',s);self.assertNotIn('timeout = 30',s)
 def test_monitor_validation(self):
  p=self.root/'monitors.conf';self.call('monitor-config','--file',str(p),'--output','eDP-1','--set','scale','1.25');self.assertIn('1.25',p.read_text());before=p.read_bytes();self.call('monitor-config','--file',str(p),'--output','eDP-1','--set','mode','bad\nvalue',ok=False);self.assertEqual(p.read_bytes(),before)
 def test_profile_rollback_and_edit_guard(self):
  cfg=self.root/'config';(cfg/'hypr/UserConfigs').mkdir(parents=True);(cfg/'hypr/hyprland.conf').write_text('# original\n');(cfg/'quickshell').mkdir();(cfg/'quickshell/qml_color.json').write_text(json.dumps(dict(windowBackground='#10151c',primaryText='#eeeeee',secondaryText='#aaaaaa',accentPrimary='#aabbcc')));(cfg/'rofi').mkdir();(cfg/'rofi/.current_wallpaper').write_text('fixture')
  self.call('profile',str(ROOT),'install','--profile','end4-lite','--no-start');p=cfg/'hypr/hyprland.conf';installed=p.read_text();fake=self.root/'broken-checkout';(fake/'vendor/end4-pC').mkdir(parents=True);self.call('profile',str(fake),'install','--profile','end4-lite','--no-start',ok=False);self.assertEqual(p.read_text(),installed);p.write_text(installed+'# user edit\n');self.call('profile',str(ROOT),'install','--profile','jakoolit','--no-start',ok=False);self.assertIn('# user edit',p.read_text());p.write_text(installed);self.call('profile',str(ROOT),'install','--profile','jakoolit','--no-start');self.assertEqual(p.read_text(),'# original\n');self.assertFalse((cfg/'quickshell/rice-desktop').exists())
if __name__=='__main__':unittest.main()
