# Lasgun Comfort

Tired of finishing a 40-minute Darktide mission with a lasgun burned into your retinas and BRRRR ringing in your ears?

Lasgun Comfort reduces firing effects for Infantry, Helbore and Recon Lasguns, plus the Accatran Mk II and Kantrael Mk X Heavy Laspistols. You can keep a thin visible beam, turn down the flashes, and optionally lower firing audio.

[Download on Nexus Mods](https://www.nexusmods.com/warhammer40kdarktide/mods/1373)

## Install

You need Darktide Mod Loader and Darktide Mod Framework (DMF). VFX Swapper and SimpleAudio are not required.

Close the game before installing or updating.

- Vortex: drag `lasgun_comfort-0.5.0.zip` into Mods, enable it and deploy.
- Manual: extract it so the entry point is `mods/lasgun_comfort/lasgun_comfort.mod`, then add `lasgun_comfort` once after `dmf` in `mods/mod_load_order.txt`.

Use one installation method. To update, replace the old version; your saved settings stay. To roll back, reinstall your previous ZIP and restart. To remove it, disable/remove it in Vortex and redeploy, or remove the manual folder and load-order entry with the game closed. Restart after removal.

Alf's DMF (Mod Settings) Extensions is optional. Enable its mod-tab feature for separate settings tabs, with this load order:

```text
dmf
Alfs_DMF_Extensions
lasgun_comfort
```

Without Alf, the same settings are available in ordinary DMF groups.

## Visual settings

Open Mod Options > Lasgun Comfort. Lasguns and Heavy Laspistols have separate beam and muzzle controls.

- Thin keeps a narrow beam. Its width ranges from 0.01 to 0.15, with 0.03 as the default. This changes width, not the beam's color or shader brightness.
- Off hides the beam and its trails.
- Original keeps the stock normal and critical beams at their original width. The separate glow/trail and muzzle switches still work.

Rifles also have charge-effect suppression. The impact switch under Lasgun visuals is shared by rifles and pistols.

Thin beams and flash suppression are enabled by default. Matching effects from teammates are affected on your screen too. Enemy beam templates and other weapon families are not targeted. The mod does not change damage, ammo, recoil, input, hit markers or weapon stats.

## Firing audio (experimental)

Turn ON the control for your weapon family before lowering its slider. With the switch OFF, the slider does nothing. Infantry, Helbore, Recon and Heavy Laspistols each have their own control; the two pistol marks share one slider.

The slider adjusts direct sound gain:

| Setting | Direct level |
| --- | --- |
| 100 | Original |
| 50 | About 6 dB lower |
| 10 | About 20 dB lower |

50 does not mean half the perceived loudness. Release the trigger and fire again after changing settings. Audio controls default to OFF, with sliders at 50.

The mod adjusts the weapon sound source. It does not change global music, dialogue or enemy audio settings. Other sounds overlapping on that same source can briefly become quieter too. Reverb, critical extras and separately played shot tails are not individually controlled.

If audio stays unexpectedly quiet, switch the control OFF and restart the game.

## Known limits and troubleshooting

Some effects can still leave an initial burst or embedded light. The original beam shader can also remain bright; try Thin or Off if Original still bothers you.

Other VFX mods can overlap with these settings. Sound replacement mods may bypass the audio matching. Multiplayer and combinations with other mods have not been fully tested.

Diagnostic logging defaults to OFF. Turn it on under Diagnostics when investigating a problem, then turn it off again. Older saved preferences may have it enabled already. Reports are most useful with the weapon and mark, firing mode, settings and other installed mods.

I tested Veteran rifle visuals in the Psykhanium and reported working Recon and Helbore audio. I also confirmed the 0.5 build was working before release. There is no complete in-game test matrix for every weapon and mode, and the final menu-label changes have not been checked in-game. See [VALIDATION.txt](VALIDATION.txt) for the automated checks and remaining limits, and [CHANGELOG.txt](CHANGELOG.txt) for version history.

## Building and contributing

The mod source is in `lasgun_comfort/`. Build the Vortex ZIP with Python 3 from the repository root:

```sh
python release_support/build_release.py
```

The ZIP and SHA-256 file go into ignored `dist/`. Credits and documentation stay outside the install ZIP. No game assets are bundled.

For regression tests, reference requirements and the local commit privacy check, see [release_support/TESTING.txt](release_support/TESTING.txt). New files are ignored until added to the reviewed `.gitignore` allowlist.

## Credits

This project started with tdopz's VFX Swapper as a reference, which credits leerH's VFX Limiter. It uses DMF and optionally Alf's settings extension.

OpenAI Codex helped write and review the code, tests and documentation. See [CREDITS.txt](CREDITS.txt) for the full acknowledgements and AI disclosure.

No open-source license has been selected yet.
