"""Native DMF setup/update checks and Alf 2.0.7 tab allocation (UI primitives mocked)."""
import argparse
import importlib
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--runtime', choices=['lua51', 'luajit21'], default='lua51')
p.add_argument('--references', type=Path, required=True)
p.add_argument('--baseline-mod-root', type=Path, required=True)
a = p.parse_args()
LuaRuntime = importlib.import_module('lupa.' + a.runtime).LuaRuntime
root = Path(__file__).resolve().parents[2] / 'lasgun_comfort'
scripts = root / 'scripts/mods/lasgun_comfort'

for with_alf in (False, True):
    lua = LuaRuntime()
    lua.execute('''
    values, writes, dmf_values = {}, {}, {}
    mod, dmf, alf = {}, {}, {}
    function get_mod(name)
      if name=='DMF' then return dmf elseif name=='Alfs_DMF_Extensions' then return alf end
      assert(name=='lasgun_comfort'); return mod
    end
    function mod:get(k) return values[k] end
    function mod:set(k,v) values[k]=v; writes[#writes+1]=k end
    function mod:get_name() return 'lasgun_comfort' end
    function mod:get_readable_name() return 'Lasgun Comfort' end
    function mod:get_description() return 'test' end
    function mod:get_metadata() return 'test' end
    function mod:get_internal_data(k) return k=='is_togglable' end
    function mod:localize(k) assert(loc[k] and loc[k].en,k); return loc[k].en end
    function dmf:get(k) return dmf_values[k] end
    function dmf:set(k,v) dmf_values[k]=v end
    function dmf.quick_localize(m,k) return m:localize(k) end
    function dmf.throw_error(...) error(string.format(...)) end
    function dmf:dump() end
    function dmf:io_dofile() return nil end
    function dmf.create_mod_options_settings(self,options) return options end
    function alf:get(k) return self.generalised end
    function alf._ensure_icon_packages_loaded() end
    function alf.is_gen_tabs_enabled_for_mod() return true end
    alf.default_tab='Other'
    function collect(widgets,result)
      result=result or {}
      for _,w in ipairs(widgets) do
        if w.type=='group' then collect(w.sub_widgets,result) else result[w.setting_id]=w end
      end
      return result
    end
    function equal(a,b)
      if type(a)~=type(b) then return false end
      if type(a)~='table' then return a==b end
      for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
      for k in pairs(b) do if a[k]==nil then return false end end
      return true
    end
    ''')
    lua.globals().loc = lua.execute((scripts/'lasgun_comfort_localization.lua').read_text())
    lua.globals().previous = lua.execute((a.baseline_mod_root/'scripts/mods/lasgun_comfort/lasgun_comfort_data.lua').read_text())
    lua.globals().config_source = (scripts/'lasgun_comfort_data.lua').read_text()
    lua.globals().config = lua.execute(lua.globals().config_source)
    lua.execute('''
    old=collect(previous.options.widgets); new=collect(config.options.widgets)
    saved={}
    for id,w in pairs(old) do
      local expected={}; for k,v in pairs(w) do expected[k]=v end
      if id=='audio_diagnostics' then expected.default_value=false end
      assert(new[id] and equal(expected,new[id]),'saved setting schema changed: '..id)
      local v=w.default_value
      if id=='audio_diagnostics' then v=true -- retain an existing explicit opt-in
      elseif w.type=='checkbox' then v=not v
      elseif id=='beam_style' then v='original'
      elseif w.type=='numeric' then v=(w.range[1]+w.range[2])/2 end
      values[id]=v; saved[id]=v
    end
    ''')
    lua.execute((a.references/'dmf_options.lua').read_text())
    if with_alf:
        main=(a.references/'alf_main.lua').read_text()
        compound=main[main.index('mod.compound_key ='):main.index('mod:io_dofile')]
        lua.execute('local mod=alf; '+compound)
        lua.execute((a.references/'alf_load_dmf.lua').read_text())
    lua.execute('''
    dmf.initialize_mod_options(mod,config.options)
    for id,value in pairs(saved) do assert(values[id]==value,'saved value reset: '..id) end
    for id,w in pairs(new) do assert(values[id]~=nil,'missing setting: '..id) end
    for _,id in ipairs(writes) do assert(not old[id] and new[id], 'unnecessary saved setting write: '..id) end
    initialized=dmf.options_widgets_data[1]
    local groups,leaves=0,0
    for _,w in ipairs(initialized) do
      if w.type=='group' then groups=groups+1; assert(values[w.setting_id]==nil)
      elseif w.type~='header' then leaves=leaves+1; assert(new[w.setting_id]) end
    end
    assert(groups==4)
    local count=0; for _ in pairs(new) do count=count+1 end
    assert(leaves==count)
    -- Fresh install: all controls receive defaults, independent of tab metadata.
    values={}; writes={}; config=assert(loadstring(config_source))(); new=collect(config.options.widgets)
    dmf.initialize_mod_options(mod,config.options)
    for id,w in pairs(new) do assert(equal(values[id],w.default_value)) end
    assert(values.audio_diagnostics==false, 'fresh install logs by default')
    ''')
    if with_alf:
        tab_source=(a.references/'alf_mod_tabs.lua').read_text()
        if a.runtime=='luajit21':
            snippet=tab_source[tab_source.index('local function get_current_mod_name'):tab_source.index('local _create_settings_widget_from_config =')]
        else:
            snippet=tab_source[tab_source.index('local function category_has_explicit_tabs'):tab_source.index('local function could_have_tabs')]
            snippet+=tab_source[tab_source.index('local function resolve_widget_tab_from_dmf_data'):tab_source.index('mod.inject_tabs_into_widgets =')]
            snippet+=tab_source[tab_source.index('mod.get_tabs ='):tab_source.index('local _create_settings_widget_from_config =')]
        lua.execute('local mod=alf; '+snippet)
        lua.execute('''
        alf.on_all_mods_loaded()
        local category='Lasgun Comfort'
        -- UI layout primitives: native initialized widget order, names and depth.
        local entries,widgets={},{}
        for _,w in ipairs(initialized) do
          if w.type~='header' then
            local entry={category=category,setting_id=w.setting_id,display_name=w.title,
              widget_type=w.type=='group' and 'group_header' or w.type,indentation_level=w.depth}
            entries[#entries+1]=entry
            widgets[#widgets+1]={entry=entry,widget={content={entry=entry}}}
          end
        end
        local templates=dmf.create_mod_options_settings({}, {settings=entries})
        view={_selected_category=category,_options_templates=templates,
          _settings_category_widgets={[category]=widgets}}
        for _,generalised in ipairs({false,true}) do
          alf.generalised=generalised
          local tabs=alf.get_tabs(view,category)
          assert(#tabs==#config.options.widgets,'missing tab or accidental Other tab')
          for i,g in ipairs(config.options.widgets) do assert(tabs[i]==g.tab) end
        end
        ''')
        if a.runtime=='luajit21':
            lua.execute('''
            alf.inject_tabs_into_widgets(view,'Lasgun Comfort')
            local expected={}
            for _,g in ipairs(config.options.widgets) do
              expected[g.setting_id]=g.tab
              for _,w in ipairs(g.sub_widgets) do expected[w.setting_id]=g.tab end
            end
            for _,w in ipairs(view._settings_category_widgets['Lasgun Comfort']) do
              assert(w.widget.content.tab==expected[w.entry.setting_id])
            end
            ''')
    print('PASS '+a.runtime+': native DMF setup/saved settings; Alf '+str(with_alf))
print('Actual in-game menu rendering remains unverified.')
