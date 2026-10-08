"""Real muzzle action vs opt-in pre-spawn suppression, using all weapon FX tables."""
import argparse, importlib, re
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--runtime',choices=['lua51','luajit21'],default='lua51')
p.add_argument('--game-source',required=True,type=Path)
a=p.parse_args()
lua=importlib.import_module('lupa.'+a.runtime).LuaRuntime()
root=Path(__file__).resolve().parents[2]/'lasgun_comfort'
lua.execute('''
values,hooks,spawned={},{},{}
mod={}
function get_mod() return mod end
function mod:get(k) return values[k] end
function mod:hook(c,m,f) hooks[c..'.'..m]=f end
function mod:info() end
World={find_particles_variable=function() return 1 end,
 set_particles_variable=function(world,id) assert(id~=nil); variable_writes=variable_writes+1 end}
Matrix4x4={translation=function() return {} end,from_quaternion_position=function() return {} end,
 multiply=function() return {} end,inverse=function() return {} end,rotation=function() return {} end}
Vector3=function(x,y,z) return {x=x,y=y,z=z} end
function make_self(fx,crit)
 return {_unit_data_extension={},_critical_strike_component={is_active=crit},
 _action_settings={fx=fx},_inventory_slot_component={},_action_module_charge_component={charge_level=.75},
 _muzzle_fx_source=function() return 'muzzle' end,_eject_fx_source=function() return 'eject' end,
 _reference_attachment_id=function() return 'root' end,
 _fx_extension={vfx_spawner_pose=function() return {} end,spawn_unit_particles=function(self,asset) spawned[#spawned+1]=asset; return #spawned end}}
end
function reset() spawned={}; variable_writes=0 end
''')
lua.execute((root/'scripts/mods/lasgun_comfort/lasgun_comfort.lua').read_text())
source=(a.game_source/'scripts/extension_systems/weapon/actions/action_shoot.lua').read_text(encoding='utf-8-sig')
start=source.index('ActionShoot._play_muzzle_flash_vfx =')
end=source.index('ActionShoot._play_muzzle_smoke =',start)
lua.execute('ActionShoot={}; '+source[start:end])
lua.globals().LineEffects=lua.execute((a.game_source/'scripts/settings/effects/player_line_effects.lua').read_text(encoding='utf-8-sig'))
checks=0
weapon_dir=a.game_source/'scripts/settings/equipment/weapon_templates'
files=sorted((weapon_dir/'lasguns').glob('lasgun_*.lua'))+sorted((weapon_dir/'laspistols').glob('laspistol_*.lua'))
assert len(files)==11
for path in files:
 text=path.read_text(encoding='utf-8-sig')
 for match in re.finditer(r'\bfx\s*=\s*\{',text):
  pos=match.end()-1; depth=1; end=pos+1
  while depth:
   if text[end]=='{': depth+=1
   elif text[end]=='}': depth-=1
   end+=1
  table=text[pos:end]
  if 'muzzle_flash_effect' not in table: continue
  lua.globals().fx=lua.execute('return '+table)
  for crit in (False,True):
   for charge in (.25,1):
    lua.globals().crit=crit; lua.globals().charge=charge
    for style in ('original','thin','off'):
     lua.globals().style=style
     lua.execute('''
     values.beam_style=style; values.laspistol_beam_style=style
     values.suppress_muzzle=false; values.suppress_laspistol_muzzle=false
     mod.on_setting_changed()
     local self=make_self(fx,crit); reset()
     ActionShoot._play_muzzle_flash_vfx(self,{},nil,charge)
     local expected=#spawned
     reset()
     local hook=hooks['ActionShoot._play_muzzle_flash_vfx']; assert(hook)
     hook(ActionShoot._play_muzzle_flash_vfx,self,{},nil,charge)
     assert(#spawned==expected,'OFF changed native particle count')
     values.suppress_muzzle=true; values.suppress_laspistol_muzzle=true
     mod.on_setting_changed(); reset()
     hook(ActionShoot._play_muzzle_flash_vfx,self,{},nil,charge)
     assert(#spawned==0 and variable_writes==0,'muzzle burst spawned while suppression enabled')
     mod.on_disabled(); reset()
     hook(ActionShoot._play_muzzle_flash_vfx,self,{},nil,charge)
     assert(#spawned==expected,'disabled mod changed native action')
     mod.on_enabled()
     ''')
     checks+=1
lua.execute('''
local hook=hooks['ActionShoot._play_muzzle_flash_vfx']
local calls=0
local function original(self,config,rotation,charge)
 calls=calls+1; assert(config=='config' and rotation=='rotation' and charge==.75)
 return 42,nil,'tail'
end
for _,fx in ipairs({{}, {muzzle_flash_effect='unrelated'},
 {muzzle_flash_effect='content/fx/particles/weapons/rifles/lasgun/lasgun_muzzle',shell_casing_effect='casing'},
 {muzzle_flash_effect='content/fx/particles/weapons/rifles/lasgun/lasgun_muzzle',muzzle_flash_effect_secondary='secondary'}}) do
 local a,b,c=hook(original,make_self(fx,false),'config','rotation',.75)
 assert(a==42 and b==nil and c=='tail')
end
assert(calls==4)
''')
# Check aliases from source, rather than treating our mock resolution as source evidence.
aliases=(a.game_source/'scripts/settings/sound/player_character_sound_event_aliases.lua').read_text(encoding='utf-8-sig')
for template,event in [('laspistol_p1_m1','play_weapon_laspistol'),('laspistol_p1_m3','play_laspistol_p1_m3')]:
 section=aliases[aliases.index('ranged_single_shot ='):aliases.index('ranged_single_shot =')+14000]
 assert re.search(template+r'\s*=\s*"wwise/events/weapon/'+event+r'"',section)
 template_text=(weapon_dir/'laspistols'/(template+'.lua')).read_text(encoding='utf-8-sig')
 assert template_text.count('shoot_sfx_alias = "ranged_single_shot"')==2
print('PASS '+a.runtime+': '+str(checks)+' native muzzle-action cases across all 11 weapons, crit/charge/beam modes; no invalid handle writes.')
print('PASS: unrelated/mixed FX passthrough and both pistol hipfire/ADS firing aliases verified against source.')
