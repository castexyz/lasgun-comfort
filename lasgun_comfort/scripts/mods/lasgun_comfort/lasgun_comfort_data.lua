local mod = get_mod("lasgun_comfort")

return {
    name = mod:localize("mod_name"),
    description = mod:localize("mod_description"),
    is_togglable = true,
    options = {
        widgets = {
            {
                setting_id = "lasgun_visuals_group",
                type = "group",
                tab = mod:localize("lasgun_visuals_group"),
                sub_widgets = {
                    {
                        setting_id = "beam_style",
                        type = "dropdown",
                        default_value = "thin",
                        options = {
                            { text = "beam_thin", value = "thin" },
                            { text = "beam_off", value = "off" },
                            { text = "beam_original", value = "original" },
                        },
                    },
                    {
                        setting_id = "beam_width", type = "numeric", default_value = 0.03,
                        range = { 0.01, 0.15 }, decimals_number = 2,
                    },
                    { setting_id = "suppress_beam_glow", type = "checkbox", default_value = true },
                    { setting_id = "suppress_muzzle", type = "checkbox", default_value = true },
                    { setting_id = "suppress_charge", type = "checkbox", default_value = true },
                    { setting_id = "suppress_impacts", type = "checkbox", default_value = true },
                },
            },
            {
                setting_id = "laspistol_visuals_group",
                type = "group",
                tab = mod:localize("laspistol_visuals_group"),
                sub_widgets = {
                    {
                        setting_id = "laspistol_beam_style", type = "dropdown", default_value = "thin",
                        options = {
                            { text = "beam_thin", value = "thin" },
                            { text = "beam_off", value = "off" },
                            { text = "beam_original", value = "original" },
                        },
                    },
                    {
                        setting_id = "laspistol_beam_width", type = "numeric", default_value = 0.03,
                        range = { 0.01, 0.15 }, decimals_number = 2,
                    },
                    { setting_id = "suppress_laspistol_beam_glow", type = "checkbox", default_value = true },
                    { setting_id = "suppress_laspistol_muzzle", type = "checkbox", default_value = true },
                },
            },
            {
                setting_id = "firing_audio_group",
                type = "group",
                tab = mod:localize("firing_audio_group"),
                sub_widgets = {
                    { setting_id = "infantry_audio_enabled", type = "checkbox", default_value = false },
                    { setting_id = "infantry_shot_level", type = "numeric", default_value = 50,
                        range = { 10, 100 }, decimals_number = 0 },
                    { setting_id = "helbore_audio_enabled", type = "checkbox", default_value = false },
                    { setting_id = "helbore_shot_level", type = "numeric", default_value = 50,
                        range = { 10, 100 }, decimals_number = 0 },
                    { setting_id = "laspistol_audio_enabled", type = "checkbox", default_value = false },
                    { setting_id = "laspistol_shot_level", type = "numeric", default_value = 50,
                        range = { 10, 100 }, decimals_number = 0 },
                    { setting_id = "experimental_recon_audio", type = "checkbox", default_value = false },
                    { setting_id = "recon_loop_level", type = "numeric", default_value = 50,
                        range = { 10, 100 }, decimals_number = 0 },
                },
            },
            {
                setting_id = "diagnostics_group",
                type = "group",
                tab = mod:localize("diagnostics_group"),
                sub_widgets = {
                    { setting_id = "audio_diagnostics", type = "checkbox", default_value = false },
                },
            },
        },
    },
}
