local mod = get_mod("lasgun_comfort")

-- Inspired by tdopz's VFX Swapper and leerH's VFX Limiter. See CREDITS.txt.
-- Developed with OpenAI Codex assistance; see VALIDATION.txt for test coverage.

-- Exact player rifle line templates; enemy beam templates pass through.
local rifle_lines = {
    lasbeam_killshot = true,
    lasbeam_elysian = true,
    lasbeam_charged = true,
    lasbeam_bfg = true,
}

-- Exact resource names, deliberately not a broad substring filter. Particle
-- resources can be shared by weapons/players; these switches affect every local
-- rendering of the listed assets, including allies and some laspistol effects.
local particles = {}
local function add_particles(prefix, names, setting)
    for i = 1, #names do
        particles[prefix .. names[i]] = setting
    end
end

add_particles("content/fx/particles/weapons/rifles/lasgun/", {
    "lasgun_muzzle", "lasgun_muzzle_crit", "lasgun_muzzle_elysian",
    "lasgun_charged_muzzle", "lasgun_charged_muzzle_crit",
    "lasgun_bfg_muzzle", "lasgun_bfg_muzzle_crit",
}, "suppress_muzzle")

add_particles("content/fx/particles/weapons/rifles/lasgun/", {
    "lasgun_chargeup", "lasgun_chargefull",
}, "suppress_charge")

add_particles("content/fx/particles/impacts/weapons/lasgun/", {
    "lasgun_impact_player", "lasgun_impact_surface_player",
    "lasgun_impact_surface_charged_player", "lasgun_impact_surface_bfg_player",
    "lasgun_sparks_armor_player", "super_armor_lasgun",
}, "suppress_impacts")

local pistol_lines = {
    lasbeam_pistol = true,
    lasbeam_pistol_ads = true,
    lasbeam_heavy_pistol = true,
}

add_particles("content/fx/particles/weapons/rifles/laspistol/", {
    "laspistol_muzzle", "laspistol_heavy_muzzle", "laspistol_heavy_muzzle_crit",
}, "suppress_laspistol_muzzle")

local active = true
local settings = {}

local function read_boolean(id)
    local value = mod:get(id)
    if value == nil then
        return true
    end
    return value == true
end

local function refresh_settings()
    local mode = mod:get("beam_style")
    if mode ~= "thin" and mode ~= "off" and mode ~= "original" then
        mode = "thin"
    end
    local width = tonumber(mod:get("beam_width"))
    if not width or width ~= width then
        width = 0.03
    end
    settings.beam_style = mode
    settings.beam_width = math.max(0.01, math.min(0.15, width))
    local pistol_mode = mod:get("laspistol_beam_style")
    if pistol_mode ~= "thin" and pistol_mode ~= "off" and pistol_mode ~= "original" then
        pistol_mode = "thin"
    end
    local pistol_width = tonumber(mod:get("laspistol_beam_width"))
    if not pistol_width or pistol_width ~= pistol_width then
        pistol_width = 0.03
    end
    settings.laspistol_beam_style = pistol_mode
    settings.laspistol_beam_width = math.max(0.01, math.min(0.15, pistol_width))
    settings.suppress_beam_glow = read_boolean("suppress_beam_glow")
    settings.suppress_laspistol_beam_glow = read_boolean("suppress_laspistol_beam_glow")
    settings.suppress_laspistol_muzzle = read_boolean("suppress_laspistol_muzzle")
    settings.suppress_muzzle = read_boolean("suppress_muzzle")
    settings.suppress_charge = read_boolean("suppress_charge")
    settings.suppress_impacts = read_boolean("suppress_impacts")
end

refresh_settings()

-- Hook the local rendering method, not the public method which also sends RPCs.
-- Copy per call so shared game templates and other mods' tables are never edited.
mod:hook("PlayerUnitFxExtension", "_spawn_unit_fx_line", function(func, self, line_effect, ...)
    if not active or type(line_effect) ~= "table" then
        return func(self, line_effect, ...)
    end
    local style, width, suppress_glow
    if rifle_lines[line_effect.name] then
        style, width, suppress_glow = settings.beam_style, settings.beam_width, settings.suppress_beam_glow
    elseif pistol_lines[line_effect.name] then
        style, width, suppress_glow = settings.laspistol_beam_style, settings.laspistol_beam_width, settings.suppress_laspistol_beam_glow
    end
    if not style or (style == "original" and not suppress_glow) then
        return func(self, line_effect, ...)
    end

    local replacement = {}
    for key, value in pairs(line_effect) do
        replacement[key] = value
    end
    replacement.emitters = nil -- No lingering glow or critical-shot trail.

    if style == "off" then
        replacement.vfx = nil
        replacement.vfx_crit = nil
    elseif style == "thin" then
        -- Reuse the already-loaded normal beam, including for critical shots.
        -- This reduces width, not shader luminance; Off is available if needed.
        replacement.vfx_crit = replacement.vfx
        replacement.vfx_width = width
    end

    return func(self, replacement, ...)
end)

-- Skip the local muzzle action before an initial burst is spawned. Returning a
-- fake particle ID from World.create_particles would break linking/size writes.
-- The World hook remains for matching effects spawned through other paths.
mod:hook("ActionShoot", "_play_muzzle_flash_vfx", function(func, self, fire_config, shoot_rotation, charge_level)
    local fx = self._action_settings and self._action_settings.fx
    if active and fx and not fx.shell_casing_effect and not fx.muzzle_flash_effect_secondary then
        local critical = self._critical_strike_component.is_active
        local special = not self._is_grenade_ability_weapon and self._inventory_slot_component.special_active
        local effect
        if special then
            effect = critical and fx.weapon_special_muzzle_flash_crit_effect or fx.weapon_special_muzzle_flash_effect
        end
        effect = effect or critical and fx.muzzle_flash_crit_effect or fx.muzzle_flash_effect
        effect = effect or fx.muzzle_flash_effect
        if type(effect) == "table" then
            local variants = effect
            effect = nil
            for i = 1, #variants do
                if variants[i].charge_level <= charge_level then effect = variants[i].effect end
            end
        end
        local setting = particles[effect]
        if (setting == "suppress_muzzle" or setting == "suppress_laspistol_muzzle") and settings[setting] then
            return
        end
    end
    return func(self, fire_config, shoot_rotation, charge_level)
end)

-- Emission-suppression approach informed by tdopz / leerH's work:
-- callers can still link, configure and later clean up the real particle ID.
-- Stopping emission does not guarantee removal of an already-emitted burst.
mod:hook("World", "create_particles", function(func, world, particle_name, ...)
    local setting = particles[particle_name]
    if not active or not setting or not settings[setting] then
        return func(world, particle_name, ...)
    end

    local id = func(world, particle_name, ...)
    if id ~= nil and id ~= false then
        World.stop_spawning_particles(world, id)
    end
    return id
end)

-- Source-level attenuation for the local Recon firing loop.
-- Original sound events and their stop logic remain intact.
-- Documented Stingray API; also referenced in Darktide's wwise_flow_callbacks.
local audio_sources = {}
local audio_warning_shown = false

local function set_audio_level(world, source, level)
    local setter = WwiseWorld and WwiseWorld.set_dry_environment_for_source
    local ok = type(setter) == "function" and pcall(setter, world, source, level)
    if not ok and not audio_warning_shown then
        audio_warning_shown = true
        mod:echo("Lasgun Comfort: audio control unavailable or failed. Firing events remain unchanged. See the mod page for audio limitations.")
    end
    return ok
end

-- Individual shots need their source gain retained until playback ends.
-- Keep exact event names: reload, dry-fire, tails and charging are independent.
local shot_events = {}
for mark = 1, 3 do
    local prefix = "wwise/events/weapon/"
    shot_events[prefix .. "play_weapon_lasgun_p1_m" .. mark] = "infantry"
    shot_events[prefix .. "play_lasgun_p2_m" .. mark] = "helbore"
    shot_events[prefix .. "play_lasgun_p2_m" .. mark .. "_charged"] = "helbore"
end
shot_events["wwise/events/weapon/play_weapon_laspistol"] = "laspistol"
shot_events["wwise/events/weapon/play_laspistol_p1_m3"] = "laspistol"
local shot_sources = {}
local diagnostic_lines = 0
local function audio_log(message)
    if mod:get("audio_diagnostics") ~= true or diagnostic_lines >= 120 then return end
    diagnostic_lines = diagnostic_lines + 1
    mod:info("Audio 0.5: %s", message)
    if diagnostic_lines == 120 then
        mod:info("Audio 0.5: log limit reached; change an audio setting to start another diagnostic batch.")
    end
end

local function shot_level(family)
    if not active or mod:get(family .. "_audio_enabled") ~= true then return 1 end
    local percent = tonumber(mod:get(family .. "_shot_level"))
    if not percent or percent ~= percent then percent = 50 end
    return math.max(10, math.min(100, percent)) / 100
end

local function restore_shot_source(self, source, reason)
    local sources = shot_sources[self]
    local entry = sources and sources[source]
    if entry then
        local ok = set_audio_level(entry.world, source, 1)
        audio_log("restore source=" .. tostring(source) .. " reason=" .. tostring(reason)
            .. " call_ok=" .. tostring(ok))
        sources[source] = nil
        if next(sources) == nil then shot_sources[self] = nil end
    end
end

local function restore_shots(self, reason)
    local sources = shot_sources[self]
    if sources then
        for source in pairs(sources) do restore_shot_source(self, source, reason) end
    end
end

local function restore_all_shots(reason)
    for self in pairs(shot_sources) do restore_shots(self, reason) end
end

local function record_shot(self, source, ...)
    local id = select(1, ...)
    if type(id) == "number" and id > 0 then
        local sources = shot_sources[self]
        local entry = sources[source]
        entry.ids[id] = { polls = 0, seconds = 0 }
        audio_log("posted id=" .. tostring(id) .. " source=" .. tostring(source))
    else
        -- No new event: restore only when no previous overlapping shot remains.
        local entry = shot_sources[self] and shot_sources[self][source]
        if entry and next(entry.ids) == nil then restore_shot_source(self, source, "post_failed") end
    end
    return ...
end

mod:hook("PlayerUnitFxExtension", "trigger_wwise_event", function(func, self, event, append_husk, ...)
    local source = select(1, ...)
    if not self._is_local_unit or self:should_play_husk_effect()
        or self._unit_data_extension.is_resimulating or type(source) ~= "number" then
        return func(self, event, append_husk, ...)
    end
    local family = shot_events[event]
    local level = family and shot_level(family) or 1
    if family then
        audio_log("shot family=" .. family .. " event=" .. event .. " source=" .. tostring(source)
            .. " enabled=" .. tostring(mod:get(family .. "_audio_enabled"))
            .. " slider=" .. tostring(mod:get(family .. "_shot_level"))
            .. " gain=" .. tostring(level))
    end
    if level == 1 then
        restore_shot_source(self, source, "other_event_or_stock_level:" .. tostring(event))
    elseif WwiseWorld and type(WwiseWorld.is_playing) == "function"
        and set_audio_level(self._wwise_world, source, level) then
        shot_sources[self] = shot_sources[self] or {}
        shot_sources[self][source] = shot_sources[self][source]
            or { world = self._wwise_world, ids = {} }
        audio_log("gain_applied source=" .. tostring(source) .. " gain=" .. tostring(level) .. " call_ok=true")
        return record_shot(self, source, func(self, event, append_husk, ...))
    elseif not audio_warning_shown then
        audio_log("individual_shot_control_unavailable event=" .. tostring(event))
        audio_warning_shown = true
        mod:echo("Lasgun Comfort: individual-shot volume control unavailable. Original shot events continue.")
    end
    return func(self, event, append_husk, ...)
end)

mod:hook("PlayerUnitFxExtension", "update", function(func, self, ...)
    local sources = shot_sources[self]
    if sources then
        for source, entry in pairs(sources) do
            for id, lifetime in pairs(entry.ids) do
                lifetime.polls = lifetime.polls + 1
                local dt = select(2, ...)
                dt = tonumber(dt) or 0
                lifetime.seconds = lifetime.seconds + math.max(0, dt)
                local ok, playing = pcall(WwiseWorld.is_playing, entry.world, id)
                if lifetime.polls == 1 or not ok or not playing then
                    audio_log("playback id=" .. tostring(id) .. " source=" .. tostring(source)
                        .. " polls=" .. tostring(lifetime.polls)
                        .. " elapsed_ms=" .. tostring(math.floor(lifetime.seconds * 1000))
                        .. " check_ok=" .. tostring(ok) .. " playing=" .. tostring(playing))
                end
                if not ok or not playing then entry.ids[id] = nil end
            end
            if next(entry.ids) == nil then restore_shot_source(self, source, "playback_ended_or_check_failed") end
        end
    end
    return func(self, ...)
end)

mod:hook("PlayerUnitFxExtension", "_unregister_sound_source", function(func, self, ...)
    -- Restore before the game destroys/reuses registered weapon source IDs.
    restore_shots(self, "source_unregistered")
    return func(self, ...)
end)

local function restore_audio(self, alias)
    local sources = audio_sources[self]
    local entry = sources and sources[alias]
    if entry then
        set_audio_level(entry.world, entry.source, 1)
        sources[alias] = nil
        if next(sources) == nil then audio_sources[self] = nil end
    end
end

local function restore_all_audio()
    for self, sources in pairs(audio_sources) do
        for alias in pairs(sources) do restore_audio(self, alias) end
    end
end

local function audio_level()
    if not active or mod:get("experimental_recon_audio") ~= true then return 1 end
    local percent = tonumber(mod:get("recon_loop_level"))
    if not percent or percent ~= percent then percent = 50 end
    return math.max(10, math.min(100, percent)) / 100
end

local function apply_audio(self, alias)
    local level = audio_level()
    if level == 1 or not self._is_local_unit or self:should_play_husk_effect() then return end
    if alias ~= "ranged_shooting" and alias ~= "ranged_braced_shooting" then return end
    local data = self._looping_sounds[alias]
    if not data or not data.is_playing or data.ignored_as_exclusive_event
        or not data.id or type(data.event_name) ~= "string"
        or not data.event_name:match("^wwise/events/weapon/play_lasgun_p3_m[123]_fire_auto$") then return end
    local group = self._sources[data.source_name]
    local source = group and group[data.source_attach_name]
    if source == nil then return end
    if set_audio_level(self._wwise_world, source, level) then
        audio_sources[self] = audio_sources[self] or {}
        audio_sources[self][alias] = { world = self._wwise_world, source = source }
    end
end

mod:hook("PlayerUnitFxExtension", "_trigger_looping_wwise_sound_start_event", function(func, self, alias, ...)
    restore_audio(self, alias)
    -- A new charge can share the source while the previous shot still plays.
    -- Keep its gain until playback ends; restoring here can raise the remaining shot tail.
    -- The stock method has no return value. Inspect its resolved event/source
    -- after it runs, so other mods' sound replacements are respected.
    func(self, alias, ...)
    apply_audio(self, alias)
end)

mod:hook("PlayerUnitFxExtension", "_trigger_looping_wwise_sound_stop_event", function(func, self, alias, ...)
    restore_audio(self, alias)
    return func(self, alias, ...)
end)

mod:hook("PlayerUnitFxExtension", "destroy", function(func, self, ...)
    restore_shots(self, "extension_destroyed")
    local sources = audio_sources[self]
    if sources then
        for alias in pairs(sources) do restore_audio(self, alias) end
    end
    return func(self, ...)
end)

mod.on_setting_changed = function()
    refresh_settings()
    diagnostic_lines = 0
    audio_log("settings infantry=" .. tostring(mod:get("infantry_audio_enabled"))
        .. ":" .. tostring(mod:get("infantry_shot_level"))
        .. " helbore=" .. tostring(mod:get("helbore_audio_enabled"))
        .. ":" .. tostring(mod:get("helbore_shot_level"))
        .. " laspistol=" .. tostring(mod:get("laspistol_audio_enabled"))
        .. ":" .. tostring(mod:get("laspistol_shot_level")))
    -- Release and fire again to apply a changed level. Never retain a stale gain.
    restore_all_audio()
    restore_all_shots("settings_changed")
end
mod.on_all_mods_loaded = refresh_settings
mod.on_enabled = function()
    refresh_settings()
    active = true
end
mod.on_disabled = function()
    active = false
    restore_all_audio()
    restore_all_shots("mod_disabled")
end
mod.on_unload = function()
    restore_all_audio()
    restore_all_shots("mod_unloaded")
end
