import argparse
import importlib
import json
from pathlib import Path
import re
parser = argparse.ArgumentParser(description='Lasgun Comfort regression and source integration checks')
parser.add_argument('--mod-root', type=Path, default=Path(__file__).resolve().parents[2] / 'lasgun_comfort')
parser.add_argument('--game-source', required=True, type=Path, help='Directory containing the game scripts/ directory')
parser.add_argument('--dmf-hooks', required=True, type=Path, help='Unmodified DMF modules/core/hooks.lua reference')
parser.add_argument('--runtime', choices=['lua51', 'luajit21'], default='lua51')
options = parser.parse_args()
LuaRuntime = importlib.import_module('lupa.' + options.runtime).LuaRuntime
root = options.mod_root
scripts = root / 'scripts/mods/lasgun_comfort'
ref = options.game_source / 'scripts'
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
values, hooks, stops = {}, {}, {}
mod = {}
function get_mod(name) assert(name == 'lasgun_comfort'); return mod end
function mod:get(key) return values[key] end
function mod:localize(key) return key end
function mod:info() end
function mod:hook(object, method, fn) hooks[object .. '.' .. method] = fn end
World = {stop_spawning_particles = function(world, id) stops[#stops+1] = {world, id} end}
function pack(...) return {n=select('#', ...), ...} end
function same(a,b)
  if type(a) ~= type(b) then return false end
  if type(a) ~= 'table' then return a == b end
  for k,v in pairs(a) do if not same(v,b[k]) then return false end end
  for k in pairs(b) do if a[k] == nil then return false end end
  return true
end
function copy(t)
  if type(t) ~= 'table' then return t end
  local c = {}; for k,v in pairs(t) do c[k] = copy(v) end; return c
end
''')
for path in root.rglob('*'):
    if path.suffix in ('.lua', '.mod'):
        lua.execute('assert(loadstring(...))', path.read_text(encoding='utf-8-sig'))
print('PASS: all shipped Lua files parse under ' + options.runtime)
lua.globals().config = lua.execute((scripts / 'lasgun_comfort_data.lua').read_text())
lua.globals().loc = lua.execute((scripts / 'lasgun_comfort_localization.lua').read_text())
lua.execute('''
assert(config.is_togglable)
for _,entry in pairs(loc) do
  for _,translated in pairs(entry) do assert(pcall(string.format, translated)) end
end
local seen={}
function check_widgets(widgets,inherited_tab)
 for _,w in ipairs(widgets) do
  assert(not seen[w.setting_id]); seen[w.setting_id]=true
  assert(loc[w.setting_id] and loc[w.setting_id .. '_description'])
  local tab=w.tab or inherited_tab
  assert(type(tab)=='string' and tab~='')
  if w.type=='group' then
   assert(w.default_value==nil and #w.sub_widgets>0)
   check_widgets(w.sub_widgets,tab)
  else
   values[w.setting_id] = w.default_value
   if w.options then
    local found = false
    for _,o in ipairs(w.options) do
     assert(loc[o.text]); if o.value == w.default_value then found = true end
    end
    assert(found)
   end
  end
 end
end
assert(#config.options.widgets==4)
check_widgets(config.options.widgets)
assert(values.audio_diagnostics==false)
for _,id in ipairs({'infantry_audio_enabled','helbore_audio_enabled','experimental_recon_audio','laspistol_audio_enabled'}) do
 assert(loc[id].en:lower():find('experimental',1,true),'missing experimental label: '..id)
end
''')
lua.execute((scripts / 'lasgun_comfort.lua').read_text())
lua.execute('''
line = hooks['PlayerUnitFxExtension._spawn_unit_fx_line']
particle = hooks['World.create_particles']
assert(line and particle)
function capture(self, effect, ...) captured = effect; args = pack(...); return 42,nil,'tail' end
original = {name='lasbeam_killshot', vfx='normal', vfx_crit='crit', vfx_width=.4,
  emitters={default={{vfx='glow'}},critical_strike={{vfx='extra'}}},sfx='audio',keep_aligned=true,extension={1}}
snapshot = copy(original)
local ret = pack(line(capture, {}, original, true, nil, 'attachment'))
assert(ret.n == 3 and ret[1]==42 and ret[2]==nil and ret[3]=='tail')
assert(args.n==3 and args[1]==true and args[2]==nil and args[3]=='attachment')
assert(captured ~= original and same(original,snapshot))
assert(captured.vfx=='normal' and captured.vfx_crit=='normal' and captured.vfx_width==.03)
assert(captured.emitters==nil and captured.sfx=='audio' and captured.keep_aligned)
assert(captured.extension==original.extension)
''')
print('PASS: thin beam, critical substitution, audio, arguments, returns and template immutability')
lua.execute('''
values.beam_style='off'; mod.on_setting_changed()
line(capture,{},original)
assert(captured.vfx==nil and captured.vfx_crit==nil and captured.emitters==nil and captured.sfx=='audio')
values.beam_style='original'; mod.on_setting_changed()
line(capture,{},original); assert(captured~=original and captured.emitters==nil and captured.vfx_width==original.vfx_width)
values.suppress_beam_glow=false; mod.on_setting_changed()
line(capture,{},original); assert(captured==original)
values.suppress_beam_glow=true; mod.on_setting_changed()
values.beam_style='thin'; mod.on_setting_changed()
for _,name in ipairs({'enemy_laser','autogun_bullet','future_unknown'}) do
  local other={name=name}; line(capture,{},other); assert(captured==other)
end
line(capture,{},nil); assert(captured==nil)
''')
print('PASS: off/original modes and unrelated/unknown beam pass-through')

lua.execute('''
pistol = {name='lasbeam_heavy_pistol',vfx='normal',vfx_crit='crit',vfx_width=.375,
 emitters={critical_strike={{vfx='pistol_trail'}}},sfx='audio',link=true}
local prior=copy(pistol)
values.beam_style='off'; values.laspistol_beam_style='thin'; values.laspistol_beam_width=.06
mod.on_setting_changed(); line(capture,{},pistol)
assert(captured.vfx_width==.06 and captured.emitters==nil and captured.link and captured.sfx=='audio')
assert(same(pistol,prior))
line(capture,{},original); assert(captured.vfx==nil)
values.beam_style='thin'; values.laspistol_beam_style='original'; mod.on_setting_changed()
line(capture,{},pistol); assert(captured~=pistol and captured.emitters==nil and captured.vfx_crit==pistol.vfx_crit)
values.suppress_laspistol_beam_glow=false; mod.on_setting_changed()
line(capture,{},pistol); assert(captured==pistol)
values.suppress_laspistol_beam_glow=true; mod.on_setting_changed()
line(capture,{},original); assert(captured.vfx=='normal')
values.laspistol_beam_style='off'; mod.on_setting_changed()
line(capture,{},pistol); assert(captured.vfx==nil and captured.sfx=='audio')
for _,case in ipairs({{'bad',.03},{-1,.01},{100,.15},{'0.07',.07},{0/0,.03}}) do
 values.laspistol_beam_style='thin'; values.laspistol_beam_width=case[1]
 mod.on_setting_changed(); line(capture,{},pistol); assert(captured.vfx_width==case[2])
end
values.laspistol_beam_style='unknown'; values.laspistol_beam_width=nil
mod.on_all_mods_loaded(); line(capture,{},pistol); assert(captured.vfx_width==.03)
values.laspistol_beam_style='thin'; values.laspistol_beam_width=.03; mod.on_setting_changed()
''')
print('PASS: independent rifle/pistol styles, widths, malformed settings and template immutability')

lua.execute('''
for _,case in ipairs({{'bad',.03},{-1,.01},{100,.15},{'0.07',.07},{0/0,.03}}) do
  values.beam_width=case[1]; mod.on_setting_changed(); line(capture,{},original)
  assert(captured.vfx_width==case[2])
end
values.beam_width=nil; values.beam_style='obsolete'; mod.on_all_mods_loaded()
line(capture,{},original); assert(captured.vfx_width==.03 and captured.vfx=='normal')
function spawn(world,name,...) spawn_args=pack(world,name,...); return 0 end
local muzzle='content/fx/particles/weapons/rifles/lasgun/lasgun_muzzle_elysian'
local before=#stops
assert(particle(spawn,'world',muzzle,'pos',nil,'scale')==0)
assert(#stops==before+1 and stops[#stops][1]=='world' and stops[#stops][2]==0)
assert(spawn_args.n==5 and spawn_args[3]=='pos' and spawn_args[4]==nil and spawn_args[5]=='scale')
particle(function() return nil end,'world',muzzle); assert(#stops==before+1)
particle(function() return false end,'world',muzzle); assert(#stops==before+1)
particle(spawn,'world','unrelated'); assert(#stops==before+1)
values.suppress_muzzle=false; mod.on_setting_changed()
particle(spawn,'world',muzzle); assert(#stops==before+1)
values.suppress_muzzle=true; mod.on_setting_changed()
values.beam_width=.07; mod.on_enabled(); line(capture,{},original); assert(captured.vfx_width==.07)
values.beam_width=.03; mod.on_enabled()
-- Another hook can wrap ours, or be the next function; neither is bypassed.
local calls=0
local function peer(nextfn,...) calls=calls+1; return nextfn(...) end
peer(function(...) return particle(spawn,...) end,'world',muzzle)
particle(function(...) return peer(spawn,...) end,'world',muzzle)
assert(calls==2)
''')
print('PASS: malformed settings, particle handles, toggles, enable refresh and hook chaining')

# Compare coverage to every muzzle asset used by all nine current rifle templates.
muzzles=set()
weapon_files=list((ref/'settings/equipment/weapon_templates/lasguns').glob('lasgun_*.lua'))
assert len(weapon_files) == 9, 'Expected all nine reference weapon files; partial references cannot pass'
for path in weapon_files:
    muzzles.update(re.findall(r'"(content/fx/particles/[^"\n]*muzzle[^"\n]*)"',path.read_text(encoding='utf-8-sig')))
for asset in sorted(muzzles):
    lua.execute("local n=#stops; particle(spawn,'world',...); assert(#stops==n+1)",asset)
print(f'PASS: all {len(muzzles)} muzzle assets from all nine current lasgun templates are covered')
for setting, asset in [
    ('suppress_charge','content/fx/particles/weapons/rifles/lasgun/lasgun_chargeup'),
    ('suppress_charge','content/fx/particles/weapons/rifles/lasgun/lasgun_chargefull'),
    ('suppress_impacts','content/fx/particles/impacts/weapons/lasgun/lasgun_impact_surface_bfg_player'),
]:
    lua.execute('''local setting,asset=...; values[setting]=true; mod.on_setting_changed()
      local n=#stops; particle(spawn,'world',asset); assert(#stops==n+1)
      values[setting]=false; mod.on_setting_changed(); particle(spawn,'world',asset); assert(#stops==n+1)
      values[setting]=true; mod.on_setting_changed()''', setting,asset)
print('PASS: independent charge and impact settings')

# Every muzzle referenced by either pistol template (hipfire/ADS, normal/critical).
pistol_files=list((ref/'settings/equipment/weapon_templates/laspistols').glob('laspistol_*.lua'))
assert len(pistol_files)==2, 'Expected both Heavy Laspistol templates'
pistol_muzzles=set()
for path in pistol_files:
    pistol_muzzles.update(re.findall(r'"(content/fx/particles/[^"\n]*muzzle[^"\n]*)"',path.read_text(encoding='utf-8-sig')))
for asset in sorted(pistol_muzzles):
    lua.execute('''
      local asset=...; local n=#stops
      values.suppress_muzzle=false; values.suppress_laspistol_muzzle=true; mod.on_setting_changed()
      particle(spawn,'world',asset); assert(#stops==n+1)
      values.suppress_laspistol_muzzle=false; values.suppress_muzzle=true; mod.on_setting_changed()
      particle(spawn,'world',asset); assert(#stops==n+1)
      values.suppress_laspistol_muzzle=true; mod.on_setting_changed()
      mod.on_disabled(); particle(spawn,'world',asset); assert(#stops==n+1)
      mod.on_enabled(); particle(spawn,'world',asset); assert(#stops==n+2)
    ''',asset)
print(f'PASS: all {len(pistol_muzzles)} Heavy Laspistol muzzle assets, independent toggles and lifecycle')


# Execute the actual source rendering method, with only engine primitives stubbed.
source=(ref/'extension_systems/fx/player_unit_fx_extension.lua').read_text(encoding='utf-8-sig')
method=source.split('PlayerUnitFxExtension._spawn_unit_fx_line = function',1)[1].split('PlayerUnitFxExtension._add_moving_sfx = function',1)[0]
lua.execute('''
DEDICATED_SERVER=false
VisualLoadoutExtractData={ROOT_ATTACH_NAME='root'}
ALIGNED_VFX_RING_BUFFER_SIZE=10
PlayerUnitFxExtension={}
local vecmeta={__sub=function(a,b) return setmetatable({x=a.x-b.x},getmetatable(a)) end}
Vector3=setmetatable({length=function(v) return math.abs(v.x) end,normalize=function(v) return v end},
  {__call=function(_,x,y,z) return setmetatable({x=x,y=y,z=z},vecmeta) end})
Unit={world_pose=function() return {} end}
Matrix4x4={translation=function() return Vector3(0,0,0) end,from_quaternion_position=function() return {} end,
 multiply=function() return {} end,inverse=function() return {} end,rotation=function() return {} end}
Quaternion={look=function() return {} end}
World.find_particles_variable=function(world,asset,name) assert(name=='hit_distance'); return 1 end
World.set_particles_variable=function(world,id,index,value) rendered.width=value.x end
World.are_particles_playing=function() return true end
function make_self()
  local self={_world='world',_vfx_spawners={muzzle={root={unit={},node=1}}},_aligned_vfx={size=0,buffer={}}}
  for i=1,10 do self._aligned_vfx.buffer[i]={end_position={store=function() end}} end
  self._spawn_unit_particles=function(_,asset) rendered.beams=rendered.beams+1; rendered.asset=asset; return 7 end
  self._spawn_particles_on_line_with_interval=function() rendered.trails=rendered.trails+1 end
  self._trigger_wwise_event_on_line=function() rendered.sounds=rendered.sounds+1 end
  return self
end
''')
lua.execute('PlayerUnitFxExtension._spawn_unit_fx_line = function'+method)
lua.globals().templates=lua.execute((ref/'settings/effects/player_line_effects.lua').read_text(encoding='utf-8-sig'))
lua.execute('''
for name,t in pairs(templates) do t.name=name end
for _,name in ipairs({'lasbeam_killshot','lasbeam_elysian','lasbeam_charged','lasbeam_bfg',
 'lasbeam_pistol','lasbeam_pistol_ads','lasbeam_heavy_pistol'}) do
  for _,crit in ipairs({false,true}) do
    for _,style in ipairs({'thin','off','original'}) do
      values.beam_style=style; values.laspistol_beam_style=style; mod.on_setting_changed()
      rendered={beams=0,trails=0,sounds=0}
      local t=templates[name]; local prior=copy(t); local self=make_self()
      line(PlayerUnitFxExtension._spawn_unit_fx_line,self,t,crit,'muzzle',Vector3(10,0,0),true,'destroy',nil,false)
      assert(same(t,prior)); assert(rendered.sounds==1)
      if style=='off' then assert(rendered.beams==0 and rendered.trails==0 and self._aligned_vfx.size==0)
      elseif style=='thin' then
        assert(rendered.beams==1 and rendered.trails==0 and rendered.width==.03)
        assert(rendered.asset==t.vfx and self._aligned_vfx.buffer[1].width==.03)
      else
        assert(rendered.beams==1 and rendered.trails==0 and rendered.width==t.vfx_width)
        assert(rendered.asset==(crit and t.vfx_crit or t.vfx))
      end
    end
  end
end
''')
print('PASS: 42 integration cases using actual game beam renderer and templates (engine mocked)')


lua.execute('''
values.beam_style='original'; values.laspistol_beam_style='original'
values.suppress_beam_glow=false; values.suppress_laspistol_beam_glow=false
mod.on_setting_changed()
for _,name in ipairs({'lasbeam_killshot','lasbeam_elysian','lasbeam_charged','lasbeam_bfg',
 'lasbeam_pistol','lasbeam_pistol_ads','lasbeam_heavy_pistol'}) do
 for _,crit in ipairs({false,true}) do
  rendered={beams=0,trails=0,sounds=0}
  local t=templates[name]; local prior=copy(t)
  line(PlayerUnitFxExtension._spawn_unit_fx_line,make_self(),t,crit,'muzzle',Vector3(10,0,0),true,'destroy',nil,false)
  assert(rendered.beams==1 and rendered.trails>0 and rendered.width==t.vfx_width)
  assert(rendered.asset==(crit and t.vfx_crit or t.vfx) and same(t,prior))
 end
end
for _,style in ipairs({'original','thin','off'}) do
 values.beam_style=style; values.laspistol_beam_style=style
 for _,case in ipairs({
  {'suppress_muzzle','content/fx/particles/weapons/rifles/lasgun/lasgun_muzzle'},
  {'suppress_laspistol_muzzle','content/fx/particles/weapons/rifles/laspistol/laspistol_heavy_muzzle_crit'},
  {'suppress_charge','content/fx/particles/weapons/rifles/lasgun/lasgun_chargeup'},
  {'suppress_impacts','content/fx/particles/impacts/weapons/lasgun/lasgun_impact_surface_bfg_player'}}) do
  for _,enabled in ipairs({true,false}) do
   values[case[1]]=enabled; mod.on_setting_changed()
   local n=#stops; particle(spawn,'world',case[2])
   assert(#stops==n+(enabled and 1 or 0))
  end
 end
end
''')
print('PASS: 14 native Original-beam trail restoration cases and all flash switches across every beam style')

lua.execute('''
fassert=assert
function new_mod(name,paths) registered_name=name; registered_paths=paths end
''')
manifest=lua.execute((root/'lasgun_comfort.mod').read_text())
manifest['run']()
assert lua.globals().registered_name=='lasgun_comfort'
for _,path in lua.globals().registered_paths.items():
    assert (root.parent/(path+'.lua')).is_file(),path
json.loads((root/'info.json').read_text())
print('PASS: entry point, registration, settings localization and metadata packaging')

# Real DMF hook module: test class-resolution delay, cooperative chains, saved
# disabled state, re-enable and framework unload without a running game.
for start_enabled in (True, False):
    runtime = LuaRuntime(unpack_returned_tuples=True)
    runtime.globals().start_enabled = start_enabled
    runtime.execute('''
    DMFMod={}
    function DMFMod:is_enabled() return self.enabled end
    function DMFMod:get_name() return self.name end
    function DMFMod:get_internal_data() return false end
    function DMFMod:info() end
    function DMFMod:warning() end
    function DMFMod:error(...) errors[#errors+1]=string.format(...) end
    function DMFMod:get(key) return values[key] end
    errors={}; values={beam_style='thin',beam_width=.03,suppress_muzzle=true}
    dmf=setmetatable({name='DMF',enabled=true},{__index=DMFMod})
    mod=setmetatable({name='lasgun_comfort',enabled=start_enabled},{__index=DMFMod})
    peer=setmetatable({name='peer',enabled=true},{__index=DMFMod})
    function get_mod(name) if name=='DMF' then return dmf else assert(name=='lasgun_comfort'); return mod end end
    function dmf.check_wrong_argument_type(mod, fn, arg, value, ...)
      for _,allowed in ipairs({...}) do if type(value)==allowed then return false end end
      error('Invalid hook API argument: '..fn..' '..arg)
    end
    function dmf.safe_call_nr(mod,context,fn,...) return fn(...) end
    CLASS={InputService={start_simulate_action=function() end,stop_simulate_action=function() end},
      InputManager={update=function() end}}
    function class(name)
      local t={new=function() return {} end}; CLASS[name]=t; return t
    end
    stops=0; spawn_count=0; peer_calls=0
    function original_spawn(world,name,...) spawn_count=spawn_count+1; return 19 end
    World={create_particles=original_spawn,stop_spawning_particles=function(world,id) assert(id==19); stops=stops+1 end}
    original_line=function(self,effect,...) captured=effect; return 'result',nil,'tail' end
    ''')
    runtime.execute(options.dmf_hooks.read_text(encoding='utf-8-sig'))
    runtime.execute('''
    peer:hook('World','create_particles',function(nextfn,...) peer_calls=peer_calls+1; return nextfn(...) end)
    ''')
    runtime.execute((scripts/'lasgun_comfort.lua').read_text())
    runtime.execute('''
    -- The game's class may appear only after the mod is loaded.
    assert(CLASS.PlayerUnitFxExtension==nil)
    class('PlayerUnitFxExtension')
    CLASS.PlayerUnitFxExtension._spawn_unit_fx_line=original_line
    CLASS.PlayerUnitFxExtension._trigger_looping_wwise_sound_start_event=function() end
    CLASS.PlayerUnitFxExtension._trigger_looping_wwise_sound_stop_event=function() end
    CLASS.PlayerUnitFxExtension.destroy=function() end
    CLASS.PlayerUnitFxExtension.trigger_wwise_event=function() end
    CLASS.PlayerUnitFxExtension.update=function() end
    CLASS.PlayerUnitFxExtension._unregister_sound_source=function() end
    class('ActionShoot')
    original_muzzle=function() muzzle_calls=(muzzle_calls or 0)+1; return 'muzzle',nil,'tail' end
    CLASS.ActionShoot._play_muzzle_flash_vfx=original_muzzle
    CLASS.ActionShoot.new()
    CLASS.PlayerUnitFxExtension.new()
    local t={name='lasbeam_killshot',vfx='beam',vfx_crit='critical',vfx_width=.4,emitters={}}
    local muzzle='content/fx/particles/weapons/rifles/lasgun/lasgun_muzzle'
    local a,b,c=CLASS.PlayerUnitFxExtension._spawn_unit_fx_line({},t)
    assert(a=='result' and b==nil and c=='tail')
    assert((captured~=t)==start_enabled)
    assert(World.create_particles('world',muzzle)==19 and spawn_count==1 and peer_calls==1)
    assert(stops==(start_enabled and 1 or 0))
    local action={_action_settings={fx={muzzle_flash_effect=muzzle}},
      _critical_strike_component={},_inventory_slot_component={}}
    CLASS.ActionShoot._play_muzzle_flash_vfx(action,{},nil,.5)
    assert((muzzle_calls or 0)==(start_enabled and 0 or 1))
    mod.enabled=false; mod:disable_all_hooks(); mod.on_disabled()
    CLASS.ActionShoot._play_muzzle_flash_vfx(action,{},nil,.5)
    assert(muzzle_calls==(start_enabled and 1 or 2))
    local n=stops; CLASS.PlayerUnitFxExtension._spawn_unit_fx_line({},t); assert(captured==t)
    World.create_particles('world',muzzle); assert(stops==n and peer_calls==2)
    mod.enabled=true; mod:enable_all_hooks(); mod.on_enabled()
    CLASS.PlayerUnitFxExtension._spawn_unit_fx_line({},t); assert(captured~=t and captured.vfx_width==.03)
    World.create_particles('world',muzzle); assert(stops==n+1 and peer_calls==3)
    dmf.hooks_unload()
    assert(World.create_particles==original_spawn)
    assert(CLASS.PlayerUnitFxExtension._spawn_unit_fx_line==original_line)
    assert(CLASS.ActionShoot._play_muzzle_flash_vfx==original_muzzle)
    assert(#errors==0)
    ''')
print('PASS: actual DMF hook module with delayed classes, enabled/disabled startup, chaining, re-enable and unload')
print('All automated checks passed. Engine/GPU behavior and multiplayer require in-game testing.')
