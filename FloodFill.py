#You may use this plugin for only non commercial purposes aka non Minecraft Marketplace content.
#This plugin only works if Minecraft Bedrock is installed on Windows10 OS!

#Twitter: @RedstonerLabs
#Discord: StealthyExpert#8940

import numpy
from typing import TYPE_CHECKING, Tuple
import itertools
from amulet.api.wrapper import Interface, EntityIDType, EntityCoordType

import wx
import ast
import json
import os
import glob
import math
import random
import collections
import re
import amulet
import datetime
import time
from amulet.api.data_types import Dimension
from amulet.api.selection import SelectionGroup
from amulet_nbt import TAG_String, TAG_Int, TAG_Byte, TAG_List, TAG_Long, TAG_Compound

from amulet_map_editor.api.wx.ui.base_select import EVT_PICK
from amulet_map_editor.api.wx.ui.simple import SimpleDialog
from amulet_map_editor.api.wx.ui.block_select import BlockDefine
from amulet_map_editor.api.wx.ui.block_select import BlockSelect
from amulet_map_editor.programs.edit.api.operations import DefaultOperationUI
from amulet_map_editor.api.wx.ui.base_select import BaseSelect
from amulet_map_editor.api import image
from amulet.utils import block_coords_to_chunk_coords
from amulet.api.block import Block

import PyMCTranslate

from amulet_map_editor.api.wx.ui.base_select import BaseSelect

FaceXIncreasing = 0
FaceXDecreasing = 1
FaceYDecreasing = 3
FaceZIncreasing = 4
FaceZDecreasing = 5
MaxDirections = 6

faceDirections = (
    (FaceXIncreasing, (1, 0, 0)),
    (FaceXDecreasing, (-1, 0, 0)),
    (FaceYDecreasing, (0, -1, 0)),
    (FaceZIncreasing, (0, 0, 1)),
    (FaceZDecreasing, (0, 0, -1))
)


if TYPE_CHECKING:
    from amulet.api.level import BaseLevel
    from amulet_map_editor.programs.edit.api.canvas import EditCanvas

MODES = {
    "FloodFill": "Fills an an area from a 1x1 selection with a flood fill."
}

class FloodFill(wx.Panel, DefaultOperationUI):
    def __init__(
        self,
        parent: wx.Window,
        canvas: "EditCanvas",
        world: "BaseLevel",
        options_path: str,
    ):
        wx.Panel.__init__(self, parent)
        DefaultOperationUI.__init__(self, parent, canvas, world, options_path)
        self.Freeze()

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        options = self._load_options({})
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._sizer.Add(top_sizer, 0, wx.EXPAND | wx.ALL, 5)

        help_button = wx.BitmapButton(
            self, bitmap=image.icon.tablericons.help.bitmap(22, 22)
        )
        top_sizer.Add(help_button)

        def on_button(evt):
            dialog = SimpleDialog(self, "Help Dialog")
            text = wx.TextCtrl(
                dialog,
                value="This script will search the amulet selection and find containers such as chest, barrels, ect and set them with the selected loot operation.\n",
                style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP,
            )
            dialog.sizer.Add(text, 1, wx.EXPAND)
            dialog.ShowModal()
            evt.Skip()

        help_button.Bind(wx.EVT_BUTTON, on_button)

        self._mode = wx.Choice(self, choices=list(MODES.keys()))
        self._mode.SetSelection(0)
        top_sizer.Add(self._mode, 1, wx.EXPAND | wx.LEFT, 5)
        self._mode.Bind(wx.EVT_CHOICE, self._on_mode_change)

        self._mode_description = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP
        )
        self._sizer.Add(self._mode_description, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        self._mode_description.SetLabel(
            MODES[self._mode.GetString(self._mode.GetSelection())]
        )
        self._mode_description.Fit()

        
        self._run_button = wx.Button(self, label="Run Operation")
        self._run_button.Bind(wx.EVT_BUTTON, self._run_operation)
        self._sizer.Add(self._run_button, 0, wx.ALL | wx.ALIGN_CENTRE_HORIZONTAL, 5)

        self.Layout()
        self.Thaw()

    @property
    def wx_add_options(self) -> Tuple[int, ...]:
        return (1,)

    def _on_mode_change(self, evt):
        self._mode_description.SetLabel(
            MODES[self._mode.GetString(self._mode.GetSelection())]
        )
        self._mode_description.Fit()
        self.Layout()
        evt.Skip()

    def _on_pick_block_button(self, evt):
        """Set up listening for the block click"""
        self._show_pointer = True

    def _get_vanilla_tables(self):
        vpaths = []
        vanilla_path = "C:/Program Files/WindowsApps/**/data/behavior_packs/vanilla/loot_tables/chests/*.*"
        loot_paths = glob.glob(vanilla_path)
        for lpath in loot_paths:
            if lpath not in vpaths:
                vpaths.append(lpath.split("vanilla\\")[1].replace("\\","/"))
        return vpaths

    def _run_operation(self, _):
        self.canvas.run_operation(lambda: self._floodfill())

    def _get_vanilla_block(self, dim, world, x, y, z, trans):
        #barrowed from the amulet api. #thanks gentlegiant.
        cx, cz = block_coords_to_chunk_coords(x, z)
        offset_x, offset_z = x - 16 * cx, z - 16 * cz

        chunk = world.get_chunk(cx, cz, dim)
        runtime_id = chunk.blocks[offset_x, y, offset_z]

        return trans.block.from_universal(chunk.block_palette[runtime_id], chunk.block_entities.get((x, y, z), None))[0]

    def _floodfill(self):
        op_mode = self._mode.GetString(self._mode.GetSelection())
        world = self.world

        sel = self.canvas.selection.selection_group
        dim = self.canvas.dimension
        x, y, z = self._pointer.pointer_base
        point = x, y, z
        print (point)
        #future code for dynamic container editing.

        containers = ["gold_ore","iron_ore","coal_ore","lapis_ore","emerald_ore","diamond_ore","redstone_ore"]

        platform = world.level_wrapper.platform
        world_version = world.level_wrapper.version

        trans = world.translation_manager.get_version(platform, world_version)

        mc_version = (platform, world_version)
        print ("started flooding area...")

        def processCoords(coords):
            newcoords = collections.deque()

            for x, y, z in coords:
                for _dir, offsets in faceDirections:
                    dx, dy, dz = offsets
                    p = (x + dx, y + dy, z + dz)
                    nx, ny, nz = p
                    b = self._get_vanilla_block(dim, world, nx, ny, nz, trans).base_name

                    if b == "air":
                        world.set_version_block(nx, ny, nz, dim, mc_version, Block("minecraft", "water[level=0]"), None)
                        newcoords.append(p)

                        cx, cz = block_coords_to_chunk_coords(nx, nz)
                        chunk = world.get_chunk(cx, cz, "minecraft:overworld")

                        chunk.changed = True
                        newcoords.append(p)

            return newcoords

        def spread(coords):
            counter=0
            while len(coords):
                coords = processCoords(coords)
                start = datetime.datetime.now()
                num = len(coords)
                d = datetime.datetime.now() - start
                progress = "Did {0} coords in {1}".format(num, d)
                counter += 1
                print (progress)
                if counter > 1000000:
                    return progress 

        for box in sel.merge_boxes().selection_boxes:
            for x, y, z in box:
                spread([point])

    print ("finished filling!")

export = {
    "name": "FloodFill",
    "operation": FloodFill,
}
