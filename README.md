# gbs-control

A simple web page for a GBS-8200 used as a CSYNC RGB upscaler. GPL-3.0.

The hardware was built to take composite-sync RGB, the signal an arcade board puts on one sync pin, and scale it for a modern display. This spinoff keeps that job on one page. There is no OLED and no encoder. The web page is the control.

The board in use is a GBS-8200 v4. The first source is a Primal Rage arcade board. The page title is GBS-Controls.

## Hardware

Two changes on the scaler, and nothing else.

Red, green, and blue each pass through a series resistor. The ohms were not written down. The arcade video is about 5 V, and it arrives at the scaler at about 1 V. CSYNC is the only termination: about 100 ohm from that pin to ground. That 100 ohm figure is remembered, not measured. A video termination is often 75 ohm.

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

Composite sync is a voltage, not a logic bit. The sync tip swings toward ground. The rest of the line sits higher. The slicer is a comparator in the ADC. Its output is the digital edge the sync processor times from.

`ADC_SOGCTRL` is the threshold, 5 bits. The firmware comment records about 10 mV per step, from about 10 mV to about 320 mV. Level 6 is about 60 mV, the setting it calls a standard cable. This board holds level 13, about 130 mV, on a 15 kHz arcade source. A higher level waits for a deeper tip. A lower level trips on a shallower tip, and also on noise.

The sync processor then measures that edge: line count, pulse width, and whether horizontal sync is present. Coast tells it to keep counting through a missing pulse. Clamp uses the back porch to put black at a known ADC code.

`optimizeSogLevel()` starts at 13 and steps down only while horizontal sync is absent. It stops at the first level that holds the edge. A Namco C137, which is that board’s NTSC sync generator, still draws a full frame while the pulse width glitches. The same thing happens on a board that XORs horizontal and vertical sync onto one pin. Stepping the threshold down on every glitch walks it off the real pulse in about a minute, and the picture drops. With **Ignore VSync** on, a frame that is still about 250 to 280 lines, or 300 to 330 lines for PAL, and that still has horizontal sync, keeps the current slicer level.

### Sync slicer voltage

![Sync slicer voltage](images/slicer-voltage.svg)

The drawing is the voltage on the CSYNC pin for one line. The dashed line is the slicer. The tip has to fall through it once. That falling edge is the edge the sync processor counts.

A lower level moves the dashed line up, toward the rest of the waveform. A short glitch and ordinary noise then look like extra sync edges, and the composite-sync lock falls apart. That walk is what **Ignore VSync** stops on a frame that is still there.

The level is not written into the picture slot or `preferencesv2.txt`. Unplugging the game drops horizontal sync, and the next source is searched from level 13 again. A lower voltage found on this game does not become the voltage for another game.

### Clocks

The sample-clock PLL locks to the recovered horizontal sync and decides how many ADC clocks fit on a line.

The output raster has its own clock. An Si5351 breakout drives TV5725 pin 40 and replaces the chip’s PLL648. Frame Lock measures the game frame and trims that Si5351 frequency until the output frame is the same length, so a tear line does not crawl.

## Open the page

The open access point is `gbscontrol`, with no password. From the phone, open `http://192.168.4.1`.

On the home network the board sends the DHCP name `gbscontrol`. Open `http://gbscontrol.local` or `http://192.168.254.158` when the router has given it that address.

## Picture

![Picture page](images/picture-page.png)

- **Darker** and **brighter** move the input gain by 8. **Auto Gain** chases white on its own and turns off when you set the gain by hand.
- **Contrast −** and **contrast +** stretch black to white on the scaled picture (`VDS_Y_GAIN`, step of 8).
- **Move**, **Size**, and **Crop** shift the picture, change its width and height, or slide the outer edge.
- **Frame Lock** keeps the game frame and the output frame the same length so a tear line does not crawl. **VTotal + VSST** also shifts the vertical sync. **VTotal** only changes the frame length. If the screen goes blank or jumps, use the other one.
- **Scanlines** turns the line overlay on or off.
- **Ignore VSync** is for boards that XOR horizontal and vertical sync onto the CSync pin. Those pulses flip during the vertical interval and there is no long vertical pulse, so the scaler locks from horizontal sync instead. Turn it off for a source with separate H and V.
- **Save picture** stores the size, position, and contrast in one slot. That slot loads again at startup.

The TV5725 factory OSD icons appear on the video for a couple of seconds at lock, and again when you tap gain, contrast, move, size, or scanlines. Those icons are hardwired in the chip. Custom text or a custom logo cannot be uploaded.

## System

![System page](images/wifi-page.png)

**Incoming signal** sits at the top of this tab and refreshes every second: lock, detected mode, line count, H/V sync, and Frame Time Lock. **Restart** and **Reset Defaults** are below that. **Backup** downloads `gbs-control.cfg`. **Restore** reads that file back and restarts the scaler. **Station** joins a home network. The over-the-air update button is not on the page.

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