from __future__ import annotations

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFilter
import PIL.ImageFont

LOGO = """\
┬ ┬┌─┐┬─┐┌─┐┌─┐┌┬┐5 ┌┐ ┬─┐┌─┐┬ ┬┌─┐┌─┐┬─┐
│ │├─┘├┬┘│ ││ │ │───├┴┐├┬┘│ ││││└─┐├┤ ├┬┘
└─┘┴  ┴└─└─┘└─┘ ┴   └─┘┴└─└─┘└┴┘└─┘└─┘┴└─
"""

image = PIL.Image.new("RGBA", (810, 120), color=(0, 0, 0, 0))

draw = PIL.ImageDraw.Draw(image)

font = PIL.ImageFont.truetype("Sauce Code Pro Medium Nerd Font Complete.ttf", 32)

draw.text((10, 0), LOGO, font=font, fill=(128, 128, 128, 255))

image.save("docs/_images/uproot-browser-logo.png")
