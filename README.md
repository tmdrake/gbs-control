# gbs-control

A simple web page for a GBS-8200 used as a CSYNC RGB upscaler. GPL-3.0.

The hardware was built to take composite-sync RGB, the signal an arcade board puts on one sync pin, and scale it for a modern display. This spinoff keeps that job on one page. There is no OLED and no encoder. The web page is the control.

The board in use is a GBS-8200 v4. The first source is a Primal Rage arcade board. The page title is GBS-Controls.

## Hardware

Two changes on the scaler, and nothing else.

Red, green, and blue each pass through a series resistor. The ohms were not written down. The arcade video is about 5 V, and it arrives at the scaler at about 1 V. CSYNC may have a series resistor of the same kind. That was not written down either. It shrinks the sync tip the same way those resistors shrink the picture. CSYNC is also terminated: about 100 ohm from the scaler side of that wire to ground. That 100 ohm figure is remembered, not measured. A video termination is often 75 ohm.

![Video input](images/input-termination.svg)

An Si5351 breakout replaces the stock clock. Clock output 0 goes to TV5725 pin 40. SDA and SCL share the scaler I2C bus, and the chip answers at address `0x60`. The firmware leaves that clock enabled. Frame Time Lock tunes it.

![Si5351 clock](images/si5351-clock.svg)

This tree starts from [cpawliuk/gbs-control-complete](https://github.com/cpawliuk/gbs-control-complete) 1.4.0. The scaler core is [ramapcsx2/gbs-control](https://github.com/ramapcsx2/gbs-control) at `e4e317a`. GitHub does not list this repository as a fork of either project. The code was committed from a snapshot, then changed for this board.

## Upscaler engine

![Upscaler engine](images/upscaler-engine.svg)

The TV5725 does the scaling. The ESP8266 writes registers over I2C. It does not sit in the pixel path.

### Pixel path

Red, green, and blue enter the triple ADC at about 1 V. On a 15 kHz source the sample clock runs at 4× the pixel rate, and the decimator folds those samples back to one sample per pixel. The capture window writes the active picture into line memory. Move, size, and crop on the web page are that window.

A 240p game is already one progressive field, so the deinterlacer stays off. A 480i field turns on motion-adaptive deinterlace.

The scaler then builds its own raster. On this board that raster is 1280×960 at 60 Hz, with peaking, scanlines, and contrast (`VDS_Y_GAIN`) applied on the way out. The video DAC turns it back into analog red, green, and blue, plus separate horizontal and vertical sync. A VGA-to-HDMI converter after the GBS makes the HDMI picture. Display Data Channel stays between that converter and the TV.

### Sync slicer

Composite sync is a voltage on one pin. The sync tip swings toward ground. The rest of the line sits higher. The slicer is a comparator in the ADC (`ADC_SOGEN` on, `ADC_SOGCTRL` as the threshold). Its output is the digital edge the sync processor times from. The ESP8266 only writes that threshold over I2C. The comparator itself is inside the TV5725.

`ADC_SOGCTRL` is 5 bits, about 10 mV per step, from about 10 mV to about 320 mV. Level 6 is about 60 mV, the setting the chip comment calls a standard cable. A higher level waits for a deeper tip. A lower level trips on a shallower tip, and also on noise.

Detection of a new CSYNC source runs like this:

1. The search starts at level 13, about 130 mV. Component YPbPr starts at 14. `optimizeSogLevel()` writes that level, then watches horizontal sync (`HSACT`).
2. While horizontal sync is absent, it steps the level down by one and looks again. It stops at the first level that holds the edge. That level is the detection result for this source. A tip that already crosses 130 mV stays at 13. This arcade source did. A series resistor on CSYNC can leave a smaller tip, so 130 mV is too high and the comparator has to come down before the edge appears. That step-down is the adjustment for the reduced voltage.
3. The sync processor times the falling edge: line count, pulse width, and whether horizontal sync is still present. On XOR composite sync the vertical pin stays quiet. A locked 15 kHz picture is mode 14, about 262 lines for NTSC, with a sync pulse about 4.7 µs wide.
4. Clamp uses the back porch after that edge to put black at a known ADC code.

A Namco C137, and any board that XORs horizontal and vertical onto one pin, still draws that frame while the pulse width glitches. The tip is deep enough. The width is wrong for a moment: a runt, or a pulse that lasts almost the whole line. The chip flags that as a bad sync-on-green sample.

Without **Ignore VSync**, seventeen of those flags inside a 3 second window lower the slicer by one step. The search was written for a tip that never crosses the line. On a glitchy width it walks the threshold up the waveform. In about 30 to 60 seconds the real tip is no longer the only edge, and the picture drops. Two hundred bad samples in a row also reset mode detect and the picture blanks.

**Ignore VSync** is on by default, and it is the coast for this case. While horizontal sync is present and the line count is still about 250 to 280, or 300 to 330 for PAL, a bad sample does not lower the slicer and does not reset mode detect. The level detection found is the level that stays. A real disconnect is different: horizontal sync is gone, or the line count leaves that range. Then the old reset path runs, and the next source is searched from level 13 again.

### Sync slicer voltage

![Sync slicer voltage](images/slicer-voltage.svg)

The drawing is the voltage on the CSYNC pin for one line. The dashed line is the slicer. The tip has to fall through it once. That falling edge is the edge the sync processor counts.

A lower level moves the dashed line up, toward the rest of the waveform. Used once, during detection, that is how a smaller tip from a series resistor still makes one falling edge. Left to keep moving on a width glitch, a short spike and ordinary noise become extra sync edges, and the composite-sync lock falls apart. That walk is what **Ignore VSync** stops on a frame that is still there.

The level is not written into the picture slot or `preferencesv2.txt`. Unplugging the game drops horizontal sync, and the next source is searched from level 13 again. A lower voltage found on this game does not become the voltage for another game.

### Clocks

The sample-clock PLL locks to the recovered horizontal sync and decides how many ADC clocks fit on a line.

The output raster has its own clock. An Si5351 breakout drives TV5725 pin 40 and replaces the chip’s PLL648. With Frame Lock off, that clock stays on the 1280×960 timing, about 60 Hz. Frame Lock measures the game frame and trims the Si5351 until the output frame is the same length, so a tear line does not crawl. A 243-line source is not 60 Hz. Matching it moves the horizontal rate the display has to lock. Leave Frame Lock off when that horizontal sync wanders. Turn it on only when a slow tear is the problem you want to remove.

## Pandora Box DX

A Pandora Box DX on the JAMMA edge can send three pictures. The manual lists 1280×720, 640×480, and 384×224. 384×224 is the 15 kHz CRT mode. The default is 1280×720. There is no downscaler in that path, so the GBS sees whichever of those three the DX is set to.

Hold the cabinet Service button, turn the cabinet on, and release Service after about 2 seconds. Each power-on steps one resolution: 640×480, then 384×224. The button on the DX board itself does the same job. The Scanning Line item in the DX menu is the Pandora’s own effect. Leave it off when the GBS is drawing scanlines.

The page names a locked RGB picture `HSync RGBS/RGBHV`. The line count under that name is what picks the input path:

- Under 280 lines is 15 kHz, NTSC-like. Pandora 384×224 landed here, around 243 lines. The line doubler stays in the path, and GBS scanlines can draw.
- From 280 through 379 lines is still 15 kHz, PAL-like. The doubler stays in.
- From 380 through 535 lines is 31 kHz. Pandora 640×480 is this case. A standard 640×480 frame is 525 lines. The picture can lock and still scale to 1280×960. The line doubler is bypassed, so GBS scanlines do not draw.
- Above 535 lines, scaling turns off. Pandora 1280×720 sits around 744 lines. The count often wanders, horizontal sync stays off, and the page says no lock.

Ignore VSync holds the slicer while horizontal sync is present and the line count stays about 250 to 280, or 300 to 330 for PAL. A 525-line frame is outside that hold. A 744-line frame is outside it too.

Set the DX to 384×224, then reset the GBS. The page should say locked, with the line count under 280. Scanlines turn on from the GBS page. The icons show when brightness, contrast, position, or size changes. On 640×480 those icons can still show after lock. The icons and the scanline mix are separate.

## Open the page

The open access point is `gbscontrol`, with no Wi-Fi password. From the phone, open `http://192.168.4.1`.

On a home network the board joins as `gbscontrol` and the router assigns the address. Open `http://gbscontrol.local` or that address. The serial log prints it as `STA mode connected; IP:`. After a reset the router can hand out a new address, so the old number stops answering until the name comes back.

The page asks for a password before it sends the file. The username is ignored. The password is `qqqqqqqq`. A router that probes the board has no password, so it gets a short refusal and does not download the page. The browser asks once and remembers it for that host.

The page is about 30 kB gzipped. It used to be about 250 kB, mostly two embedded fonts and a second logo. Those are gone. The menu keeps a 64 pixel dragon. Buttons use short words. The browser is told to recheck the page, so a reload can be a short `304` instead of another full copy. A second request while a copy is already going out does not start another one.

The ESP8266 core’s small TCP stack uses 536-byte segments. A phone stalled part way through the old page on that stack. This build uses the core’s 1460-byte stack, which is the segment size the web library was written for. The finished page connection is closed from the main loop. Closing it inside the Wi-Fi callback reset the chip.

## Fault log

Faults are appended to `/faults.txt` in the chip’s flash. The file stays around 1.5 kB. Each boot records the reset reason. If scanlines are wanted and the line doubler is bypassed, it records `scan skipped` and the line count. The first on-screen icon request is recorded too.

Plug in USB, open the serial port at 115200, and send the letter `H`. The chip prints the stored lines. That print stays on USB.

## Scanlines and the on-screen display

Scanlines are mixed in the TV5725 line doubler, while the picture is still 15 kHz. The doubler stores each incoming line. The deinterlacer mixer then darkens every other stored line. The saved strength is that mix (`MADPT_Y_MI_OFFSET`). The firmware calls `enableScanlines()` only while the doubler is in the path (`IF_LD_RAM_BYPS` is 0). The dark lines are scaled up with the rest of the picture. They are not drawn on the 1280×960 output grid.

A normal output preset, such as 1280×960, chooses that path from the locked line count. Under 380 lines keeps the doubler. From 380 through 535 lines loads the 31 kHz path and bypasses the doubler. That is Pandora 640×480. Above 535 lines leaves scaling entirely. That is Pandora 1280×720.

The Scanlines switch is one saved preference. It can stay on while 640×480 is showing. The lines still do not appear. Strength only writes the mixer after the overlay is already on, so Intensity on this mode stores a new number and draws nothing. The first time a wanted overlay finds the doubler bypassed, `/faults.txt` records `scan skipped` and that line count. One line per boot. A later change to 384×224 in the same boot does not add a second line. A boot that starts on 384×224 has no skip line.

The page also allows scanlines for 480i with Bob. That is an interlaced field on the 15 kHz path, with the line count stepping between the odd and even values around 525, and the deinterlacer set to Bob. Motion-adaptive deinterlace uses the same mixer, so it turns the overlay off. Pandora 640×480 is progressive 31 kHz. It does not enter the Bob path.

A saved custom preset skips the line-count choice. The doubler bit is then whatever that register file contains. A file saved from 384×224 keeps the doubler enabled, so the overlay can try to run on 640×480. A file saved from 640×480 or 720p keeps the doubler bypassed, so 384×224 draws no GBS scanlines until a 15 kHz preset is loaded again. Saving a preset turns the overlay off inside the file on purpose. The global switch is applied again later, and only when the doubler is in the path.

A picture slot can store its own scanline copy. That copy is applied when the slot is loaded. Connecting the DX, or stepping its resolution, does not load a slot. Reset the GBS after a DX resolution change so the line count is read again.

Pandora’s Scanning Line menu draws its own lines into the raster before the GBS. On 384×224 leave it off, so it does not sit under the GBS overlay. On 640×480 the GBS overlay has no doubler to draw with. The DX menu is the effect that still can. Those lines are scaled with the picture, so they come out soft.

The on-screen display is a factory icon on the video for a couple of seconds. It appears at lock, and again when gain, contrast, move, size, or scanlines is changed. It is not a constant overlay. Lock is enough for an icon. Lock is not enough for scanlines.

The blue light on the ESP8266 is the lock LED. It is on while the scaler reports sync, and off when that sync is declared lost. A short reboot can leave it looking steady, because the picture chip keeps running and the LED comes back on as soon as lock returns.

## Help

The page says locked when the detected mode is set and horizontal sync is present. Mode `HSync RGBS/RGBHV` with about 243 to 262 lines is the 15 kHz picture from a Pandora Box DX on 384×224. About 744 lines is 1280×720. A line count that jumps, with horizontal sync off, is the scaler hunting. Reset the GBS after changing the DX resolution. The lock often appears only after that reset.

Scanlines need the 15 kHz lock, under 380 lines, so the line doubler is in the path. Pandora 640×480 locks nearer 525 lines. The doubler stays bypassed, the saved switch can stay on, and the lines do not show. The full path and the gotchas are under Scanlines and the on-screen display. The Pandora menu item Scanning Line is a different effect. Leave it off on 384×224 so the two do not stack. On 640×480 it is the effect the DX can still draw, and the scaler will soften it.

The on-screen display is not a menu that stays up. It is a short icon on the video when brightness, contrast, move, size, or scanlines changes. It needs the same locked picture.

Output horizontal sync is the GBS raster, not the game’s sync. With Frame Lock off, it stays on the 1280×960 clock. With Frame Lock on, the Si5351 is trimmed to this frame, about 64 Hz for 243 lines instead of 60 Hz, and some displays lose horizontal lock. If the width or the horizontal lock looks wrong, turn Frame Lock off first. Position and width are the Picture arrows after that.

The picture controls use arrow marks. Each button has one name. Picture and System are the menu buttons. Move, Size, and Crop choose what the arrows do. Profile sits under those controls. Ignore VSync is at the bottom of Picture, next to its note. Save, Recall, and Rename use six named profiles, and the row marked startup loads again after a restart. Backup and restore carry the profiles in `gbs-control.cfg`.

To read a fault after the fact, connect USB at 115200 and send `H`. The log is also in `/faults.txt` on the chip. A boot line is the reset reason. `scan skipped` means scanlines were saved and the line doubler was bypassed.

## Picture

![Picture page](images/picture-page.png)

- **Darker** and **brighter** move the input gain by 8. **Auto Gain** chases white on its own and turns off when you set the gain by hand.
- **Contrast −** and **contrast +** stretch black to white on the scaled picture (`VDS_Y_GAIN`, step of 8).
- **Move**, **Size**, and **Crop** shift the picture, change its width and height, or slide the outer edge.
- **Frame Lock** keeps the game frame and the output frame the same length so a tear line does not crawl. **VTotal + VSST** also shifts the vertical sync. **VTotal** only changes the frame length. If the screen goes blank or jumps, use the other one.
- **Scanlines** turns the line overlay on or off. The choice is saved. It draws on a 15 kHz source, under 380 lines. Pandora 640×480 is about 525 lines, the doubler is bypassed, and the lines do not draw. When the locked picture is 380 lines or more, and it is not NTSC or PAL, a note under **Scanlines** says the lines stay off. See Scanlines and the on-screen display.
- **Ignore VSync** is the CSYNC coast described under Sync slicer. XOR composite sync has no long vertical pulse, and the pulse width glitches while the frame is still drawing. With this on, that glitch does not move the slicer. Turn it off for a source with separate H and V.
- **Profile** stores the current picture under a name. Six profiles are listed, A through F. **Save** writes the chosen one and makes it the startup profile. **Recall** loads it now. **Rename** changes the name and leaves the saved picture in place. Startup loads that same profile again. An older save that used another slot still appears in the list.

The TV5725 factory OSD icons appear on the video for a couple of seconds at lock, and again when you tap gain, contrast, move, size, or scanlines. Those icons are hardwired in the chip. Custom text or a custom logo cannot be uploaded.

## System

![System page](images/wifi-page.png)

**Incoming signal** sits at the top of this tab and refreshes every second: lock, detected mode, line count, H/V sync, and Frame Time Lock. **Restart** and **Reset Defaults** are below that. **Backup** downloads `gbs-control.cfg`. **Restore** writes that file back and restarts. The file holds preferences, the profile names, and each saved picture, so the last profile still loads at startup. **Station** joins a home network and the board restarts. On the access point, open `http://192.168.4.1`. After it joins, open `http://gbscontrol.local`. The page password is `qqqqqqqq` and the username is ignored. The phone sign-in sheet is not this page. The over-the-air update button is not on the page.

The notes below are the 1.4.0 package this project started from.

# GBS-Control-Complete 1.4.0

This repository contains a modified build of [GBS-Control](https://github.com/ramapcsx2/gbs-control) along with the required libraries for building and running it on an ESP8266 using the Arduino IDE.

Precompiled builds are available by version in the `build` directory. Below, any listed changes correspond to the respective build versions.


## Included Components

- [`gbs-control`](https://github.com/ramapcsx2/gbs-control) — Original video processor firmware, modified for ESP8266.
- [`ESPAsyncWebServer`](https://github.com/me-no-dev/ESPAsyncWebServer) — Asynchronous web server library.
- [`ESPAsyncTCP`](https://github.com/me-no-dev/ESPAsyncTCP) — Async TCP library required by the web server.
- [`esp8266-oled-ssd1306`](https://github.com/ThingPulse/esp8266-oled-ssd1306) — OLED display library for ESP8266.
- [`package_esp8266com_index.json`](http://arduino.esp8266.com/stable/package_esp8266com_index.json) — Additional Boards Manager URL for ESP8266.


## Modifications and Features Added
- [`1.4.0`] Restored [Added remove presets feature - PR #496](https://github.com/ramapcsx2/gbs-control/pull/496) which was missing because the contributor edited the generated webui.html directly instead of index.html.tpl. Changes were lost on build. Initial implementation by [AlivE-git](https://github.com/AlivE-git).
- [`1.3.0`] Restored [Added color correction settings - PR #490](https://github.com/ramapcsx2/gbs-control/pull/490) which were missing because the contributor edited the generated webui.html directly instead of index.html.tpl. Changes were lost on build. Initial implementation by [AlivE-git](https://github.com/AlivE-git).
- [`1.2.0`] Improved the Web GUI in the FrameTime Lock section by replacing the single "Switch Lock Method" cycling button with explicit toggles for each method. This change makes it immediately clear which FrameTime Lock method is active, improving usability and removing the need to consult logs.

**Before:**

The active method was hidden; switching required pressing the arrow button and observing the effect.

![FrameTime Lock Method Screenshot 1](images/FrameTime-Lock-Method-README-IMG-1.png)

**After:**

Each method now has its own toggle button. The currently selected method is highlighted, allowing faster and more intuitive control.

![FrameTime Lock Method Screenshot 2](images/FrameTime-Lock-Method-README-IMG-2.png)
![FrameTime Lock Method Screenshot 3](images/FrameTime-Lock-Method-README-IMG-3.png)


- [`1.1.0`] Added an OSD menu option to enable scanlines and adjust strength using the same intensity levels as the Web GUI.

![Scanlines OSD Screenshot](images/Scanlines-README-IMG.png)


- [`1.0.0`] Updated include paths and `#include` directives to match current IDE/library expectations.
- [`1.0.0`] Adjusted build flags and settings for ESP8266 compatibility.
- [`1.0.0`] Patched code inconsistencies in `gbs-control` that caused compiler errors.
- [`1.0.0`] Ensured all dependencies are self-contained in this repository for reproducible builds.

You can compare these changes from the original sources by checking the [commit history](https://github.com/cpawliuk/gbs-control-complete/commits/main/).


## Planned Features
- Rework of the OLED menu system.
- Add an OSD menu option for Frametime Lock with a toggle between vtotal + VSST and vtotal only methods.
- Add an OSD menu option for Deinterlace Method with a toggle between Motion Adaptive and Bob modes.


## Credits

- [rama](https://github.com/ramapcsx2) — `gbs-control`
- [me-no-dev](https://github.com/me-no-dev) — `ESPAsyncTCP` and `ESPAsyncWebServer`
- [Daniel Eichhorn](https://github.com/squix78) & [Fabrice Weinberg](https://github.com/FWeinb) — `esp8266-oled-ssd1306`
- [Christopher Pawliuk](https://github.com/cpawliuk) — Modifications and Features Added in this package


## Versions

- [`gbs-control`] — based on commit e4e317a.
- [`ESPAsyncWebServer`] — based on commit ad3741d.
- [`ESPAsyncTCP`] — as of commit 191bdeb.
- [`esp8266-oled-ssd1306`] — as of commit f90368e.