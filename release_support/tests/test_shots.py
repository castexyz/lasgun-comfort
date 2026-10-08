"""Individual-shot integration using game event dispatch and gear resolution."""
import argparse
import importlib
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--runtime', choices=['lua51', 'luajit21'], default='lua51')
p.add_argument('--game-source', required=True, type=Path)
a = p.parse_args()
lua = importlib.import_module('lupa.' + a.runtime).LuaRuntime()
root = Path(__file__).resolve().parents[2] / 'lasgun_comfort'
source = (a.game_source / 'scripts/extension_systems/fx/player_unit_fx_extension.lua').read_text()
lua.execute('''
hooks, values, levels, playing, events = {}, {}, {}, {}, {}
warnings, next_id, diagnostics = 0, 100, {}
mod = {}
function get_mod() return mod end
function mod:get(k) return values[k] end
function mod:hook(c,m,f) hooks[m]=f end
function mod:echo() warnings=warnings+1 end
function mod:info(format,...) diagnostics[#diagnostics+1]=string.format(format,...) end
function pack(...) return {n=select('#',...),...} end
PlayerUnitFxExtension={}
VisualLoadoutExtractData={ROOT_ATTACH_NAME=''}
WwiseWorld={}
function setter(world,source,level) levels[source]=level end
WwiseWorld.set_dry_environment_for_source=setter
function WwiseWorld.is_playing(world,id) return playing[id]==true end
function WwiseWorld.trigger_resource_event(world,event,...)
 next_id=next_id+1; playing[next_id]=true
 local source=select(1,...)
 events[#events+1]={name=event,level=levels[source] or 1,args=pack(...)}
 if fail_post then return nil,nil,'failed' end
 return next_id,nil,'third_return'
end
function make_self(event,source)
 return {_is_local_unit=true,_is_server=false,_wwise_world='world',
 _unit_data_extension={},_sources={muzzle={['']=source}},
 should_play_husk_effect=function(self) return self.husk end,
 _visual_loadout_extension={resolve_gear_sound=function() return true,event,true end}}
end
''')
for method, end in [('trigger_wwise_event', 'PlayerUnitFxExtension.trigger_wwise_events_local_only'),
                    ('trigger_gear_wwise_event_with_source', 'PlayerUnitFxExtension.trigger_gear_wwise_event_with_position')]:
    start = source.index('PlayerUnitFxExtension.' + method + ' =')
    lua.execute(source[start:source.index(end, start)])
lua.execute((root / 'scripts/mods/lasgun_comfort/lasgun_comfort.lua').read_text())
lua.execute('''
local original=PlayerUnitFxExtension.trigger_wwise_event
function PlayerUnitFxExtension.trigger_wwise_event(self,...)
 return hooks.trigger_wwise_event(original,self,...)
end
function tick(s)
 return hooks.update(function(self,arg) assert(self==s and arg=='unit'); return 77,nil,'update' end,s,'unit')
end
function fire(s,event,source,...)
 return s:trigger_wwise_event(event,true,source,...)
end
function make(event,source)
 return setmetatable(make_self(event,source),{__index=PlayerUnitFxExtension})
end
local prefix='wwise/events/weapon/'
local event=prefix..'play_weapon_lasgun_p1_m1'
local s=make(event,1)
local id=fire(s,event,1); assert(events[#events].level==1) -- default opt-in
values.infantry_audio_enabled=true; values.helbore_audio_enabled=true
values.infantry_shot_level=50; values.helbore_shot_level=10
for mark=1,3 do
 for _,kind in ipairs({'infantry','helbore','charged'}) do
  local name=kind=='infantry' and 'play_weapon_lasgun_p1_m'..mark
    or 'play_lasgun_p2_m'..mark..(kind=='charged' and '_charged' or '')
  local expected=kind=='infantry' and .5 or .1
  s=make(prefix..name,mark)
  local r=pack(s:trigger_gear_wwise_event_with_source('ranged_single_shot',{},'muzzle',false,false))
  assert(r.n==3 and r[2]==nil and r[3]=='third_return')
  assert(events[#events].level==expected and levels[mark]==expected)
  tick(s); assert(levels[mark]==expected)
  playing[r[1]]=false; local t=pack(tick(s))
  assert(levels[mark]==1 and t.n==3 and t[1]==77 and t[2]==nil and t[3]=='update')
 end
end

-- Both Heavy Laspistol aliases, default OFF and enabled at 100/50/10.
for _,name in ipairs({'play_weapon_laspistol','play_laspistol_p1_m3'}) do
 local pistol=prefix..name; local p=make(pistol,80)
 values.laspistol_audio_enabled=false; values.laspistol_shot_level=10
 local shot=fire(p,pistol,80); assert(events[#events].level==1)
 values.laspistol_audio_enabled=true
 for _,case in ipairs({{100,1},{50,.5},{10,.1}}) do
  values.laspistol_shot_level=case[1]
  local r=pack(p:trigger_gear_wwise_event_with_source('ranged_single_shot',{},'muzzle',false,false))
  assert(r.n==3 and r[2]==nil and r[3]=='third_return')
  assert(events[#events].level==case[2]); tick(p)
  assert((levels[80] or 1)==case[2])
  playing[r[1]]=false; tick(p); assert((levels[80] or 1)==1)
 end
 values.laspistol_shot_level=10
 local first=fire(p,pistol,80); local second=fire(p,pistol,80)
 playing[first]=false; tick(p); assert(levels[80]==.1)
 playing[second]=false; tick(p); assert(levels[80]==1)
 local shot=fire(p,pistol,80)
 fire(p,prefix..'play_reload_foley_laspistol_clip_in',80)
 assert(events[#events].level==1 and levels[80]==1)
 shot=fire(p,pistol,80); values.laspistol_audio_enabled=false
 mod.on_setting_changed(); assert(levels[80]==1)
 for _,mode in ipairs({'remote','husk','resim'}) do
  values.laspistol_audio_enabled=true; local other=make(pistol,90)
  if mode=='remote' then other._is_local_unit=false elseif mode=='husk' then other.husk=true
  else other._unit_data_extension.is_resimulating=true end
  fire(other,pistol,90); assert(levels[90]==nil)
 end
 values.laspistol_audio_enabled=false
end

-- Overlapping shots must retain gain until the last shot ends.
s=make(event,1)
local first=fire(s,event,1); local second=fire(s,event,1)
playing[first]=false; tick(s); assert(levels[1]==.5)
playing[second]=false; tick(s); assert(levels[1]==1)
-- Any other event on the same source restores normal volume before playback.
id=fire(s,event,1); fire(s,prefix..'play_lasgun_reload_clip_in',1)
assert(events[#events].level==1 and levels[1]==1)
-- Other registered sources retain independent gain.
id=fire(s,event,1); fire(s,prefix..'play_lasgun_reload_clip_in',2)
assert(levels[1]==.5 and events[#events].level==1)
mod.on_setting_changed(); assert(levels[1]==1)
id=fire(s,event,1); mod.on_disabled(); assert(levels[1]==1)
fire(s,event,1); assert(events[#events].level==1); mod.on_enabled()
id=fire(s,event,1); mod.on_unload(); assert(levels[1]==1)
id=fire(s,event,1)
hooks._unregister_sound_source(function(self,name) assert(levels[1]==1 and name=='muzzle') end,s,'muzzle')
id=fire(s,event,1)
hooks.destroy(function(self) assert(levels[1]==1) end,s)
-- Remote, husk, resimulation and other weapon events must pass through.
for _,mode in ipairs({'remote','husk','resim'}) do
 s=make(event,30)
 if mode=='remote' then s._is_local_unit=false
 elseif mode=='husk' then s.husk=true
 else s._unit_data_extension.is_resimulating=true end
 fire(s,event,30); assert(levels[30]==nil)
end
s=make(event,1)
for _,name in ipairs({'play_weapon_lasgun_p1_m4','play_weapon_laspistol',
 'play_lasgun_p2_charge','play_player_wpn_refl_las','play_weapon_autogun'}) do
 fire(s,prefix..name,1); assert(events[#events].level==1)
end
-- No-source calls preserve their argument count (do not add a nil argument).
s:trigger_wwise_event('unrelated',false)
assert(events[#events].args.n==0)
local r=pack(fire(s,event,1,nil,'extra'))
assert(events[#events].args.n==3 and events[#events].args[3]=='extra')
mod.on_setting_changed()
for _,case in ipairs({{-1,.1},{200,1},{'bad',.5},{0/0,.5},{'25',.25}}) do
 values.infantry_shot_level=case[1]
 id=fire(s,event,1); assert(events[#events].level==case[2])
 mod.on_setting_changed()
end
-- Regression: Helbore slider must apply distinct gains to both shot variants.
for _,suffix in ipairs({'','_charged'}) do
 local helbore=prefix..'play_lasgun_p2_m1'..suffix
 local h=make(helbore,60)
 for _,case in ipairs({{100,1},{50,.5},{10,.1}}) do
  values.helbore_shot_level=case[1]
  local shot=fire(h,helbore,60)
  assert(events[#events].level==case[2], 'Helbore slider gain mismatch')
  tick(h); assert((levels[60] or 1)==case[2])
  playing[shot]=false; tick(h); assert((levels[60] or 1)==1)
 end
end
values.helbore_shot_level=10
values.infantry_shot_level=50
-- Native post failure restores gain and preserves returns.
fail_post=true; r=pack(fire(s,event,1)); fail_post=false
assert(r.n==3 and r[1]==nil and r[3]=='failed' and levels[1]==1)
-- Checker errors cannot strand a source at lower gain.
id=fire(s,event,1)
local checker=WwiseWorld.is_playing
WwiseWorld.is_playing=function() error('native checker failed') end
tick(s); assert(levels[1]==1)
WwiseWorld.is_playing=nil; fire(s,event,1); assert(events[#events].level==1 and warnings==1)
WwiseWorld.is_playing=checker
WwiseWorld.set_dry_environment_for_source=function() error('unsupported') end
fire(s,event,1); assert(events[#events].level==1)
WwiseWorld.set_dry_environment_for_source=setter
-- Regression: starting the next Helbore charge must not raise an active shot's gain.
for mark=1,3 do
 for _,suffix in ipairs({'','_charged'}) do
  local helbore=prefix..'play_lasgun_p2_m'..mark..suffix
  local h=make(helbore,60)
  local first=fire(h,helbore,60)
  hooks._trigger_looping_wwise_sound_start_event(function(self,alias,name)
   assert(self==h and levels[60]==.1 and alias=='ranged_charging' and name=='muzzle',
    'next charge prematurely restored an active Helbore shot')
  end,h,'ranged_charging','muzzle')
  tick(h); assert(levels[60]==.1)
  local second=fire(h,helbore,60)
  playing[first]=false; tick(h); assert(levels[60]==.1)
  playing[second]=false; tick(h); assert(levels[60]==1)
 end
end
s=make(event,1)
-- Logging must remain quiet when the setting is absent (before initialization).
assert(#diagnostics==0)
values.audio_diagnostics=true
-- Timing diagnostics must preserve update arguments and accurately accumulate dt.
mod.on_setting_changed()
id=fire(s,event,1)
hooks.update(function(self,unit,dt,time) assert(unit=='unit' and dt==.016 and time==2) end,s,'unit',.016,2)
local found=false
for _,message in ipairs(diagnostics) do
 if message:find('elapsed_ms=16',1,true) then found=true end
end
assert(found)
playing[id]=false; tick(s); assert(levels[1]==1)
-- Diagnostic logging can be disabled and is bounded within a settings batch.
values.audio_diagnostics=false
local before=#diagnostics
id=fire(s,event,1); playing[id]=false; tick(s)
assert(#diagnostics==before)
values.audio_diagnostics=true; mod.on_setting_changed(); before=#diagnostics
for i=1,70 do id=fire(s,event,1); playing[id]=false; tick(s) end
assert(#diagnostics-before<=121)
''')
print('PASS ' + a.runtime + ': 11 actual gear-dispatch paths, charged shots, overlapping playback,')
print('source isolation/restoration, lifecycle, native failures, original arguments/returns.')
print('Audible Heavy Laspistol reduction requires an in-game test.')
