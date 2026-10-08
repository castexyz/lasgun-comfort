"""Exercise the real game loop start/stop methods with a mocked native engine."""
import argparse
import importlib
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--runtime', choices=['lua51', 'luajit21'], default='lua51')
p.add_argument('--game-source', required=True, type=Path)
a = p.parse_args()
lua = importlib.import_module('lupa.' + a.runtime).LuaRuntime()
root = Path(__file__).resolve().parents[2] / 'lasgun_comfort'
lua.execute('''
hooks, values, calls, levels, warnings = {}, {}, {}, {}, 0
mod = {}
function get_mod() return mod end
function mod:get(k) return values[k] end
function mod:info() end
function mod:hook(c,m,f) hooks[m]=f end
function mod:echo() warnings=warnings+1 end
PlayerUnitFxExtension = {}
VisualLoadoutExtractData={ROOT_ATTACH_NAME=''}
PlayerCharacterLoopingSoundAliases={}
for _,alias in ipairs({'ranged_shooting','ranged_braced_shooting','other'}) do
 PlayerCharacterLoopingSoundAliases[alias]={has_husk_events=true,
 start={event_alias='play'},stop={event_alias='stop'}}
end
WwiseWorld={}
function setter(world,source,level) levels[source]=level end
WwiseWorld.set_dry_environment_for_source=setter
function WwiseWorld.trigger_resource_event(world,event,source)
 calls[#calls+1]={event,source}; return 123
end
function WwiseWorld.stop_event(world,id) calls[#calls+1]={'forced_stop',id} end
function make_self(event,local_player,husk,source)
 local self={_is_local_unit=local_player,_wwise_world='world',
 _sources={muzzle={['']=source}},_looping_sounds={},_looping_sound_trigger_data={},
 should_play_husk_effect=function() return husk end,
 _visual_loadout_extension={resolve_gear_sound=function(_,action)
 return true,'wwise/events/weapon/'..action..'_'..event end}}
 for _,alias in ipairs({'ranged_shooting','ranged_braced_shooting','other'}) do
 self._looping_sounds[alias]={}; self._looping_sound_trigger_data[alias]={} end
 return self
end
''')
source = (a.game_source / 'scripts/extension_systems/fx/player_unit_fx_extension.lua').read_text()
for method, end in [('_trigger_looping_wwise_sound_start_event', 'PlayerUnitFxExtension._stop_looping_wwise_event'),
                    ('_trigger_looping_wwise_sound_stop_event', 'local function _register_vfx_spawner_from_attachments')]:
    start = source.index('PlayerUnitFxExtension.' + method + ' =')
    lua.execute(source[start:source.index(end, start)])
lua.execute((root / 'scripts/mods/lasgun_comfort/lasgun_comfort.lua').read_text())
lua.execute('''
function start(s,alias)
 hooks._trigger_looping_wwise_sound_start_event(PlayerUnitFxExtension._trigger_looping_wwise_sound_start_event,s,alias or 'ranged_shooting','muzzle')
end
function stop(s,alias,force)
 hooks._trigger_looping_wwise_sound_stop_event(PlayerUnitFxExtension._trigger_looping_wwise_sound_stop_event,s,alias or 'ranged_shooting',force,false)
end
local s=make_self('lasgun_p3_m1_fire_auto',true,false,1)
start(s); assert(levels[1]==nil); stop(s) -- opt-in default
values.experimental_recon_audio=true
for mark=1,3 do
 for _,alias in ipairs({'ranged_shooting','ranged_braced_shooting'}) do
  s=make_self('lasgun_p3_m'..mark..'_fire_auto',true,false,mark)
  values.recon_loop_level=50; start(s,alias)
  assert(levels[mark]==.5 and s._looping_sounds[alias].id==123)
  stop(s,alias); assert(levels[mark]==1 and not s._looping_sounds[alias].is_playing)
  assert(calls[#calls][1]=='wwise/events/weapon/stop_lasgun_p3_m'..mark..'_fire_auto')
 end
end
for _,case in ipairs({{false,false,'lasgun_p3_m1_fire_auto'},
 {true,true,'lasgun_p3_m1_fire_auto'},{true,false,'autogun_p1_m1_auto'},
 {true,false,'lasgun_p3_m4_fire_auto'},{true,false,'replacement_sound'}}) do
 s=make_self(case[3],case[1],case[2],40); start(s); assert(levels[40]==nil); stop(s)
end
s=make_self('lasgun_p3_m1_fire_auto',true,false,1)
for _,case in ipairs({{10,.1},{100,1},{-1,.1},{200,1},{'bad',.5},{0/0,.5}}) do
 values.recon_loop_level=case[1]; start(s); assert(levels[1]==case[2]); stop(s)
end
values.recon_loop_level=50
start(s); stop(s,nil,true); assert(levels[1]==1 and calls[#calls][1]=='forced_stop')
start(s); mod.on_setting_changed(); assert(levels[1]==1); stop(s)
start(s); mod.on_disabled(); assert(levels[1]==1); stop(s)
start(s); assert(levels[1]==1); stop(s); mod.on_enabled()
start(s); mod.on_unload(); assert(levels[1]==1); stop(s)
start(s)
local destroyed=false
hooks.destroy(function(self,arg) assert(self==s and arg=='unit' and levels[1]==1); destroyed=true; return 9 end,s,'unit')
assert(destroyed)
-- Missing source / unresolved event cannot change a different sound source.
s=make_self('lasgun_p3_m1_fire_auto',true,false,80); s._sources.muzzle['']=nil
-- Use a start stub here because the native game requires a valid source.
hooks._trigger_looping_wwise_sound_start_event(function(self)
 self._looping_sounds.ranged_shooting={is_playing=true,id=123,
 event_name='wwise/events/weapon/play_lasgun_p3_m1_fire_auto',source_name='muzzle',source_attach_name=''}
end,s,'ranged_shooting')
assert(levels[80]==nil)
s=make_self('lasgun_p3_m1_fire_auto',true,false,90)
WwiseWorld.set_dry_environment_for_source=nil
start(s); assert(s._looping_sounds.ranged_shooting.id==123 and warnings==1); stop(s)
WwiseWorld.set_dry_environment_for_source=function() error('unavailable') end
start(s); assert(s._looping_sounds.ranged_shooting.id==123 and warnings==1); stop(s)
WwiseWorld.set_dry_environment_for_source=setter
start(s); assert(levels[90]==.5); stop(s); assert(levels[90]==1)
''')
print('PASS ' + a.runtime + ': real loop methods, all Recon marks/ADS aliases, local targeting,')
print('bounds, opt-in, restoration, forced stop, missing source/API and native errors.')
print('Native sound gain and audible outcome still require an in-game test.')
