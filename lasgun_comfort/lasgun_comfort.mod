return {
    run = function()
        fassert(rawget(_G, "new_mod"), "Lasgun Comfort requires Darktide Mod Framework.")
        new_mod("lasgun_comfort", {
            mod_script = "lasgun_comfort/scripts/mods/lasgun_comfort/lasgun_comfort",
            mod_data = "lasgun_comfort/scripts/mods/lasgun_comfort/lasgun_comfort_data",
            mod_localization = "lasgun_comfort/scripts/mods/lasgun_comfort/lasgun_comfort_localization",
        })
    end,
    packages = {},
}
