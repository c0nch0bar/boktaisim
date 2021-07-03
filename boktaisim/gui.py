#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import importlib.resources as pkg_resources
import logging
import os
import pathlib
from PIL import Image, ImageTk
import platform
import requests
import simpleaudio
import sys
import time
import tkinter
from tkinter import font, messagebox
import tkinter.ttk
from typing import Dict, Optional, Union
import webbrowser

from .classes import BoktaiConfig, BoktaiSim, c_to_f, f_to_c, WeatherInfo, zip_to_latlong
from .constants import BOKTAI_METER, IMAGES, LOCAL_TIMEZONE, SOUNDS, WEATHER_STATES,\
    WEATHER_STATES_REVERSE
from .version import __version__


if sys.platform == 'win32' and hasattr(sys, 'frozen'):
    os.chdir(str(pathlib.Path(sys.executable).parent))


class WindowManager(object):
    def __init__(
            self,
            config_file: Optional[str] = None
    ) -> None:
        self.logger = logging.getLogger()
        self.window = tkinter.Tk()
        self.boktaisim: Optional[BoktaiSim] = None
        self.config = BoktaiConfig.from_json(config_file)
        self.logger.setLevel(logging.getLevelName(self.config.logging_level))
        self._current_theme = None
        self._last_value = None
        self._last_version = None
        self._last_temp_scale = None
        self._first_update = True
        self._link_cursor = 'hand1'
        self._main_font = None
        self._caption_font = None
        self._last_win_size = ''
        self._canvas_width = 0
        self._image_containers: Dict[str, ImageHandler] = {}
        self._tk_variables = {}
        self._sim_dict = {}
        self._sound_dict = {}
        self._widget_dict = {}
        self._imgs = {}
        self._select_link_cursor()
        self._init_image_paths()
        self._init_sound_dict()
        self._set_icon()

    def _select_link_cursor(self) -> None:
        if sys.platform == 'darwin':
            self._link_cursor = 'pointinghand'
        elif sys.platform == 'win32':
            self._link_cursor = 'hand2'
        else:
            self._link_cursor = 'hand1'

    def _init_sound_dict(self) -> None:
        self._sound_dict = SOUNDS.copy()
        if sys.platform == 'win32' and hasattr(sys, 'frozen'):
            for sound_name, sound_data in SOUNDS.items():
                if not sound_data:
                    self._sound_dict[sound_name] = None
                    continue
                sound_path = f'resources/{sound_data["file"]}'
                audio_segment = simpleaudio.WaveObject.from_wave_file(str(sound_path))
                self._sound_dict[sound_name]['segment'] = audio_segment
            self._sound_dict['bar_update']['file'] = \
                f'resources/{self.config.alert_sound_option}.wav'
            audio_segment = simpleaudio.WaveObject.from_wave_file(
                self._sound_dict['bar_update']['file']
            )
            self._sound_dict['bar_update']['segment'] = audio_segment
        else:
            for sound_name, sound_data in SOUNDS.items():
                if not sound_data:
                    self._sound_dict[sound_name] = None
                    continue
                with pkg_resources.path('boktaisim.resources', sound_data['file']) as sound_path:
                    audio_segment = simpleaudio.WaveObject.from_wave_file(str(sound_path))
                    self._sound_dict[sound_name]['segment'] = audio_segment
            self._sound_dict['bar_update']['file'] = f'{self.config.alert_sound_option}.wav'
            with pkg_resources.path(
                    'boktaisim.resources', f'{self.config.alert_sound_option}.wav'
            ) as sound_path:
                audio_segment = simpleaudio.WaveObject.from_wave_file(str(sound_path))
                self._sound_dict['bar_update']['segment'] = audio_segment

    def _init_image_paths(self) -> None:
        for image_name in IMAGES:
            if sys.platform == 'darwin' and hasattr(sys, 'frozen') and sys.frozen == 'macosx_app':
                self._imgs[image_name] = image_name
            elif sys.platform == 'win32' and hasattr(sys, 'frozen'):
                self._imgs[image_name] = f'resources/{image_name}'
            else:
                with pkg_resources.path('boktaisim.resources', image_name) as image_path:
                    self._imgs[image_name] = image_path
            continue

    def _set_icon(self) -> None:
        system = platform.system()
        if system == 'Windows':
            self.window.iconbitmap(self._imgs["boktaisim_icon.ico"])
            pass
        elif system == 'Darwin':
            # Looks like there's no actual way to set an icon on Mac with tkinter :'(
            # self.window.iconbitmap(self._imgs["boktaisim_icon.gif"])
            pass
        else:
            self.window.iconbitmap(self._imgs["boktaisim_icon.xbm"])

    def main(self) -> None:
        self._main_font = font.Font(self.window, family='TkDefaultFont')
        self._caption_font = font.Font(self.window, family='TkSmallCaptionFont')
        self.window.geometry('405x480')
        self.window.minsize(405, 480)
        self.window.bind('<Configure>', self._resize_window)
        style = tkinter.ttk.Style(self.window)
        hours = list(range(0, 24))
        minutes = list(range(0, 60))

        style.theme_use("classic")
        self.window.configure(bg='#ECECEC')
        tkinter.ttk.Style().configure('custom.TButton', foreground='black', background='#ECECEC')
        tkinter.ttk.Style().configure('custom.TRadiobutton', foreground='black')
        tkinter.ttk.Style().configure('custom.TCheckbutton', foreground='black')
        tkinter.ttk.Style().configure('centered.TNotebook', tabposition='n')
        tkinter.ttk.Style().configure('custom.TNotebook')
        tkinter.ttk.Style().configure('custom.TCombobox')

        style.theme_create(
            "boktai",
            parent="classic",
            settings={
                "TNotebook": {
                    "configure": {
                        "tabmargins": [2, 5, 2, 0]
                    }
                },
                "TNotebook.Tab": {
                    "configure": {
                        "padding": [5, 1],
                        "background": "green"
                    },
                    "map": {
                        "background": [
                            ("selected", "red")
                        ],
                        "expand": [
                            ("selected", [1, 1, 1, 0])
                        ]
                    }
                }
            }
        )

        self.window.title('Stiles\' Solar Sensor Simulator for the Boktai Trilogy')
        tkinter.ttk.Style().theme_use(self.config.theme)
        master_notebook = tkinter.ttk.Notebook(
            self.window, style='custom.TNotebook', name='master_notebook'
        )
        simulator_frame = tkinter.Frame(master_notebook, name='simulator_frame')
        options_frame = tkinter.Frame(master_notebook, padx=10, pady=10, name='options_frame')
        logging_frame = tkinter.Frame(master_notebook, name='logging_frame')
        logging_text = tkinter.Text(
            logging_frame, state='disabled', font='TkFixedFont', wrap='none', name='logging_text'
        )
        logging_vertical_scroll = tkinter.ttk.Scrollbar(
            logging_frame, command=logging_text.yview, orient="vertical"
        )
        logging_horizontal_scroll = tkinter.ttk.Scrollbar(
            logging_frame, command=logging_text.xview, orient="horizontal"
        )
        logging_text.configure(
            yscrollcommand=logging_vertical_scroll.set, xscrollcommand=logging_horizontal_scroll.set
        )
        logging_text.tag_config('INFO', foreground='black')
        logging_text.tag_config('DEBUG', foreground='blue')
        logging_text.tag_config('WARNING', foreground='orange')
        logging_text.tag_config('ERROR', foreground='red')
        logging_text.tag_config('CRITICAL', foreground='red', underline=1)
        text_handler = TextHandler(logging_text)
        text_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                           "%Y-%m-%d %H:%M:%S")
        text_handler.setFormatter(text_formatter)
        self.logger.addHandler(text_handler)
        logging.info('Solar Sensor Simulator starting up')
        master_notebook.add(simulator_frame, text='Simulator')
        master_notebook.add(options_frame, text='Options')
        master_notebook.add(logging_frame, text='Logging')
        simulator_frame.bind('<Return>', self.do_update)

        middle_spacing_label = tkinter.Label(simulator_frame, text=" ", name='middle_spacing_label')
        self._image_containers['bt1_logo'] = ImageHandler.from_file(
            file_path=self._imgs["boktai1_logo.gif"],
            version=1,
            parent=simulator_frame,
            name='boktai1_logo',
            container_type='Label'
        )
        self._image_containers['bt2_logo'] = ImageHandler.from_file(
            file_path=self._imgs["boktai2_logo.gif"],
            version=2,
            parent=simulator_frame,
            name='boktai2_logo',
            container_type='Label'
        )
        self._image_containers['bt3_logo'] = ImageHandler.from_file(
            file_path=self._imgs["boktai3_logo.gif"],
            version=3,
            parent=simulator_frame,
            name='boktai3_logo',
            container_type='Label'
        )
        area_notebook = tkinter.ttk.Notebook(
            simulator_frame, style='centered.TNotebook', name='area_notebook'
        )
        zipcode_frame = tkinter.Frame(area_notebook, name='zipcode_frame')
        latlon_frame = tkinter.Frame(area_notebook, name='latlon_frame')
        manual_frame = tkinter.Frame(area_notebook, name='mamnual_frame')
        area_notebook.add(zipcode_frame, text='Zipcode')
        area_notebook.add(latlon_frame, text='Lat/Lon')
        area_notebook.add(manual_frame, text='Manual')
        version_and_submit_frame = tkinter.Frame(simulator_frame, name='version_and_submit_frame')
        version_label = tkinter.Label(
            version_and_submit_frame, text="Boktai: ", name='version_label'
        )
        version_combo = tkinter.ttk.Combobox(
            version_and_submit_frame,  width=2, style='custom.TCombobox', name='version_combo'
        )
        version_combo['values'] = (1, 2, 3)
        version_combo.current(self.config.version - 1)
        button = tkinter.ttk.Button(
            version_and_submit_frame,
            text="Generate",
            style='custom.TButton',
            command=self.do_update,
            name='button'
        )
        zipcode_label = tkinter.Label(zipcode_frame, text="Zipcode: ", name='zipcode_label')
        zipcode_entry = tkinter.Entry(
            zipcode_frame, width=5, text=self.config.zipcode, name='zipcode_entry'
        )
        if self.config.zipcode:
            zipcode_entry.insert(0, self.config.zipcode)
        zipcode_note_label = tkinter.Label(
            zipcode_frame, text='USA zipcodes only, for \nother locations, use Lat/Lon',
            font="TkSmallCaptionFont", name='zipcode_note_label'
        )
        lat_label = tkinter.Label(latlon_frame, text='Latitude: ', name='lat_label')
        lat_entry = tkinter.Entry(latlon_frame, width=10, name='lat_entry')
        if self.config.lat:
            lat_entry.insert(0, self.config.lat)
        lon_label = tkinter.Label(latlon_frame, text='Longitude: ', name='lon_label')
        lon_entry = tkinter.Entry(latlon_frame, width=10, name='lon_entry')
        latlon_note_label = tkinter.Label(
            latlon_frame,
            text='Click here to find your lat/lon',
            fg="blue", cursor=self._link_cursor, name='latlon_note_label'
        )
        if self.config.lon:
            lon_entry.insert(0, self.config.lon)
        min_f_label = tkinter.Label(
            manual_frame, text=f'Min °{self.config.temp_scale}: ', name='min_f_label'
        )
        min_f = None
        avg_f = None
        max_f = None
        if self.config.temp_scale == 'C':
            if self.config.min_f:
                min_f = round(f_to_c(self.config.min_f), 2)
            if self.config.avg_f:
                avg_f = round(f_to_c(self.config.avg_f), 2)
            if self.config.max_f:
                max_f = round(f_to_c(self.config.max_f), 2)
        else:
            if self.config.min_f:
                min_f = self.config.min_f
            if self.config.avg_f:
                avg_f = self.config.avg_f
            if self.config.max_f:
                max_f = self.config.max_f
        min_f_entry = tkinter.Entry(manual_frame, width=4, name='min_f_entry')
        if min_f:
            min_f_entry.insert(0, min_f)
        avg_f_label = tkinter.Label(
            manual_frame, text=f'Avg °{self.config.temp_scale}: ', name='avg_f_label'
        )
        avg_f_entry = tkinter.Entry(manual_frame, width=4, name='avg_f_entry')
        if avg_f:
            avg_f_entry.insert(0, avg_f)
        max_f_label = tkinter.Label(
            manual_frame, text=f'Max °{self.config.temp_scale}: ', name='max_f_label'
        )
        max_f_entry = tkinter.Entry(manual_frame, width=4, name='max_f_entry')
        if max_f:
            max_f_entry.insert(0, max_f)
        weather_state_frame = tkinter.Frame(manual_frame, name='weather_state_frame')
        weather_state_entry_label = tkinter.Label(
            weather_state_frame,
            text='Weather: ',
            name='weather_state_entry_label'
        )
        self._tk_variables['weather_state_option'] = tkinter.StringVar()
        if self.config.weather:
            self._tk_variables['weather_state_option'].set(
                WEATHER_STATES[self.config.weather]['name']
            )
        else:
            self._tk_variables['weather_state_option'].set('Clear')
        weather_states = WEATHER_STATES_REVERSE.keys()
        weather_state_option = tkinter.ttk.OptionMenu(
            weather_state_frame,
            self._tk_variables['weather_state_option'],
            self._tk_variables['weather_state_option'].get(),
            *weather_states,
            style='custom.TButton',
            command=self._set_alert_sound,
        )

        sunrise_frame = tkinter.Frame(manual_frame, name='sunrise_frame')
        sunrise_label = tkinter.Label(
            sunrise_frame,
            text='Sunrise: ',
            name='sunrise_label'
        )
        self._tk_variables['sunrise_hour_option'] = tkinter.StringVar()
        if self.config.sunrise and ':' in self.config.sunrise:
            sunrise_hour, sunrise_minute  = self.config.sunrise.split(':')
        else:
            sunrise_hour = 0
            sunrise_minute = 0
        self._tk_variables['sunrise_hour_option'].set(sunrise_hour)
        sunrise_hour_option = tkinter.ttk.OptionMenu(
            sunrise_frame,
            self._tk_variables['sunrise_hour_option'],
            self._tk_variables['sunrise_hour_option'].get(),
            *hours,
            style='custom.TButton',
            command=self._set_alert_sound,
        )
        sunrise_hour_option.config(width=2)
        sunrise_colon_label = tkinter.Label(sunrise_frame, text=':', name='sunrise_colon_label')
        self._tk_variables['sunrise_minute_option'] = tkinter.StringVar()
        self._tk_variables['sunrise_minute_option'].set(sunrise_minute)
        sunrise_minute_option = tkinter.ttk.OptionMenu(
            sunrise_frame,
            self._tk_variables['sunrise_minute_option'],
            self._tk_variables['sunrise_minute_option'].get(),
            *minutes,
            style='custom.TButton',
            command=self._set_alert_sound
        )
        sunrise_minute_option.config(width=2)

        sunset_frame = tkinter.Frame(manual_frame, name='sunset_frame')
        sunset_label = tkinter.Label(
            sunset_frame,
            text='Sunset: ',
            name='sunset_label'
        )
        self._tk_variables['sunset_hour_option'] = tkinter.StringVar()
        if self.config.sunset and ':' in self.config.sunset:
            sunset_hour, sunset_minute  = self.config.sunset.split(':')
        else:
            sunset_hour = 0
            sunset_minute = 0
        self._tk_variables['sunset_hour_option'].set(sunset_hour)
        sunset_hour_option = tkinter.ttk.OptionMenu(
            sunset_frame,
            self._tk_variables['sunset_hour_option'],
            self._tk_variables['sunset_hour_option'].get(),
            *hours,
            style='custom.TButton',
            command=self._set_alert_sound,
        )
        sunset_hour_option.config(width=2)
        sunset_colon_label = tkinter.Label(sunset_frame, text=':', name='sunset_colon_label')
        self._tk_variables['sunset_minute_option'] = tkinter.StringVar()
        self._tk_variables['sunset_minute_option'].set(sunset_minute)
        sunset_minute_option = tkinter.ttk.OptionMenu(
            sunset_frame,
            self._tk_variables['sunset_minute_option'],
            self._tk_variables['sunset_minute_option'].get(),
            *minutes,
            style='custom.TButton',
            command=self._set_alert_sound,
        )
        sunset_minute_option.config(width=2)

        more_info_frame = tkinter.Frame(simulator_frame, name='more_info_frame')
        location_label = tkinter.Label(more_info_frame, text='', name='location_label')
        min_temp_label = tkinter.Label(
            more_info_frame, text=f'Min °{self.config.temp_scale}: ??', name='min_temp_label'
        )
        current_temp_label = tkinter.Label(
            more_info_frame, text=f'Current °{self.config.temp_scale}: ??',
            name='current_temp_label'
        )
        max_temp_label = tkinter.Label(
            more_info_frame, text=f'Max °{self.config.temp_scale}: ??', name='max_temp_label'
        )
        weather_state_icon = tkinter.PhotoImage(file=self._imgs[f"c.gif"])
        weather_state_label = tkinter.Label(
            more_info_frame, text='Current Weather: ??', name='weather_state_label',
            image=weather_state_icon, compound=tkinter.RIGHT
        )
        sun_state_icon = tkinter.PhotoImage(file=self._imgs[f"At Apex.gif"])
        sun_state_label = tkinter.Label(
            more_info_frame, text='Sun Status: ??', name='sun_state_label',
            image=sun_state_icon, compound=tkinter.RIGHT
        )
        boktai_meter_frame = tkinter.Frame(simulator_frame, width=274, name='boktai_meter_frame')
        self._image_containers['bt1meter_bg'] = ImageHandler.from_file(
            file_path=self._imgs["boktai1_meter_empty.gif"],
            version=1,
            parent=boktai_meter_frame,
            name='boktai1_meter_bg',
            container_type='Canvas',
            width=270,
            height=51
        )
        self._image_containers['bt1meter_fg'] = ImageHandler.from_file(
            file_path=self._imgs["boktai1_meter_full.gif"],
            version=1,
            parent=boktai_meter_frame,
            name='boktai1_meter_fg',
            container_type='Canvas',
            width=0,
            height=51
        )
        self._image_containers['bt2meter_bg'] = ImageHandler.from_file(
            file_path=self._imgs["boktai2_meter_empty.gif"],
            version=2,
            parent=boktai_meter_frame,
            name='boktai2_meter_bg',
            container_type='Canvas',
            width=280,
            height=51
        )
        self._image_containers['bt2meter_fg'] = ImageHandler.from_file(
            file_path=self._imgs["boktai2_meter_full.gif"],
            version=2,
            parent=boktai_meter_frame,
            name='boktai2_meter_fg',
            container_type='Canvas',
            width=0,
            height=51
        )
        self._image_containers['bt3meter_bg'] = ImageHandler.from_file(
            file_path=self._imgs["boktai3_meter_empty.gif"],
            version=3,
            parent=boktai_meter_frame,
            name='boktai3_meter_bg',
            container_type='Canvas',
            width=280,
            height=51
        )
        self._image_containers['bt3meter_fg'] = ImageHandler.from_file(
            file_path=self._imgs["boktai3_meter_full.gif"],
            version=3,
            parent=boktai_meter_frame,
            name='boktai3_meter_fg',
            container_type='Canvas',
            width=0,
            height=51
        )

        ui_update_frame = tkinter.Frame(options_frame, name='ui_update_frame')
        ui_update_timer_header = tkinter.Label(
            ui_update_frame, text='UI Update Interval (Minutes)', name='ui_update_timer_header'
        )
        self._tk_variables['gui_update_interval'] = tkinter.IntVar()
        ui_update_timer_slider = tkinter.Scale(
            ui_update_frame, from_=0, to=30, tickinterval=5, orient=tkinter.HORIZONTAL, length=150,
            command=self._wrap_option('gui_update_interval'),
            variable=self._tk_variables['gui_update_interval'],
            name='gui_update_interval'
        )
        self._tk_variables['gui_update_interval'].set(round(self.config.gui_update_interval / 60))
        ui_update_timer_label = tkinter.Label(
            ui_update_frame, text='0 = Disable \nAutomatic UI Updates', name='ui_update_timer_label'
        )
        ui_api_update_seperator = tkinter.ttk.Separator(options_frame)
        api_update_frame = tkinter.Frame(options_frame, name='api_update_frame')
        api_update_timer_header = tkinter.Label(
            api_update_frame, text='API Update Interval (Minutes)', name='api_update_timer_header'
        )
        self._tk_variables['api_update_interval'] = tkinter.IntVar()
        api_update_timer_slider = tkinter.Scale(
            api_update_frame, from_=0, to=60, tickinterval=10, orient=tkinter.HORIZONTAL,
            length=150,
            resolution=5,
            command=self._wrap_option('api_update_interval'),
            variable=self._tk_variables['api_update_interval'],
            name='api_update_interval'
        )
        self._tk_variables['api_update_interval'].set(round(self.config.api_update_interval / 60))
        api_update_timer_label = tkinter.Label(
            api_update_frame, text='0 = Disable \nAutomatic API Updates',
            name='api_update_timer_label'
        )
        api_update_mute_separator = tkinter.ttk.Separator(options_frame)
        self._tk_variables['mute_flavor_sounds'] = tkinter.IntVar()
        if self.config.mute_flavor_sounds:
            self._tk_variables['mute_flavor_sounds'].set(1)
        mute_frame = tkinter.Frame(options_frame, name='mute_frame')
        mute_flavor_checkbutton = tkinter.ttk.Checkbutton(
            mute_frame,
            text='Mute Flavor Sounds',
            command=self._wrap_option('mute_flavor_sounds'),
            variable=self._tk_variables['mute_flavor_sounds'],
            style='custom.TCheckbutton',
            name='mute_flavor_sounds'
        )
        alert_sound_label = tkinter.Label(
            mute_frame, text='Alert Sound: ', name='alert_sound_label'
        )
        self._tk_variables['alert_sound_option'] = tkinter.StringVar()
        if self.config.alert_sound_option:
            self._tk_variables['alert_sound_option'].set(self.config.alert_sound_option)
        alert_sound_option = tkinter.ttk.OptionMenu(
            mute_frame,
            self._tk_variables['alert_sound_option'],
            self._tk_variables['alert_sound_option'].get(),
            'chime1',
            'chime2',
            'boktai',
            'taiyou',
            style='custom.TButton',
            command=self._set_alert_sound,
        )
        self._tk_variables['mute_alert_sounds'] = tkinter.IntVar()
        if self.config.mute_alert_sounds:
            self._tk_variables['mute_alert_sounds'].set(1)
        mute_alert_checkbutton = tkinter.ttk.Checkbutton(
            mute_frame,
            text='Mute Alert Sounds',
            command=self._wrap_option('mute_alert_sounds'),
            variable=self._tk_variables['mute_alert_sounds'],
            style='custom.TCheckbutton',
            name='mute_alert_sounds'
        )
        mute_lunar_mode_separator = tkinter.ttk.Separator(options_frame)
        self._tk_variables['lunar_mode'] = tkinter.IntVar()
        if self.config.lunar_mode:
            self._tk_variables['lunar_mode'].set(1)
        lunar_mode_checkbutton = tkinter.ttk.Checkbutton(
            options_frame,
            text='Enable Lunar Mode*',
            command=self._wrap_option('lunar_mode'),
            variable=self._tk_variables['lunar_mode'],
            style='custom.TCheckbutton',
            name='lunar_mode'
        )
        lunar_mode_notes_label = tkinter.Label(
            options_frame, text='*Boktai is not meant to be played at night and by default this \n'
                                'program reflects that. This setting uses lower readings based \n'
                                'off of weather, excluding sunlight.',
            font="TkSmallCaptionFont", name='lunar_mode_notes_label'
        )
        lunar_mode_theme_separator = tkinter.ttk.Separator(options_frame)
        theme_picker_frame = tkinter.Frame(options_frame, name='theme_picker_frame')
        self._tk_variables['theme'] = tkinter.StringVar()
        if self.config.theme:
            self._tk_variables['theme'].set(self.config.theme)
        theme_label = tkinter.Label(theme_picker_frame, text='Theme: ', name='theme_label')
        themes_available = tkinter.ttk.Style().theme_names()
        theme_option = tkinter.ttk.OptionMenu(
            theme_picker_frame, self._tk_variables['theme'],
            self._tk_variables['theme'].get(), *themes_available,
            style='custom.TButton',
            command=self._update_theme
        )
        temp_scale_frame = tkinter.Frame(
            theme_picker_frame, name='temp_scale_frame'
        )
        self._tk_variables['temp_scale'] = tkinter.StringVar()
        if self.config.temp_scale:
            self._tk_variables['temp_scale'].set(self.config.temp_scale)
        fahrenheit_radio = tkinter.ttk.Radiobutton(
            temp_scale_frame,
            text='Fahrenheit',
            command=self._update_temp_scale,
            variable=self._tk_variables['temp_scale'],
            value='F',
            style='custom.TRadiobutton',
            name='fahrenheit_radio'
        )
        celsuis_radio = tkinter.ttk.Radiobutton(
            temp_scale_frame,
            text='Celsius',
            command=self._update_temp_scale,
            variable=self._tk_variables['temp_scale'],
            value='C',
            style='custom.TRadiobutton',
            name='celsuis_radio'
        )
        theme_logging_separator = tkinter.ttk.Separator(options_frame)
        logging_level_frame = tkinter.Frame(options_frame, name='logging_level_frame')
        self._tk_variables['logging_level'] = tkinter.StringVar()
        if self.config.theme:
            self._tk_variables['logging_level'].set(self.config.logging_level)
        logging_level_label = tkinter.Label(
            logging_level_frame, text='Logging Level:', name='logging_level_label'
        )
        logging_level_option = tkinter.ttk.OptionMenu(
            logging_level_frame,
            self._tk_variables['logging_level'],
            self._tk_variables['logging_level'].get(),
            'CRITICAL',
            'ERROR',
            'WARNING',
            'INFO',
            'DEBUG',
            style='custom.TButton',
            command=self._update_logging_level
        )

        if self.config.lunar_mode:
            self._tk_variables['lunar_mode'].set(1)

        about_button = tkinter.ttk.Button(
            self.window,
            text='About',
            style="custom.TButton",
            command=self.about_window,
            name="about_button"
        )
        bottom_frame = tkinter.Frame(self.window)

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        master_notebook.grid(column=0, row=0, sticky=tkinter.NSEW, padx=(5, 5), pady=(5, 5))
        master_notebook.columnconfigure(0, weight=1)
        master_notebook.rowconfigure(0, weight=1)
        area_notebook.grid(column=0, row=6, columnspan=8, sticky=tkinter.NSEW, padx=(30, 30))
        area_notebook.columnconfigure(0, weight=1)
        area_notebook.rowconfigure(0, weight=1)
        simulator_frame.columnconfigure(0, weight=1)
        simulator_frame.columnconfigure(1, weight=1)
        simulator_frame.columnconfigure(2, weight=1)
        simulator_frame.columnconfigure(3, weight=1)
        simulator_frame.columnconfigure(4, weight=1)
        simulator_frame.columnconfigure(5, weight=1)
        simulator_frame.rowconfigure(0, weight=1)
        simulator_frame.rowconfigure(1, weight=1)
        simulator_frame.rowconfigure(2, weight=1)
        simulator_frame.rowconfigure(3, weight=1)
        simulator_frame.rowconfigure(4, weight=1)
        simulator_frame.rowconfigure(5, weight=1)
        version_and_submit_frame.grid(column=0, row=1, columnspan=8, padx=(15, 15))
        version_label.grid(column=0, row=0)
        version_combo.grid(column=1, row=0, padx=(0, 15))
        button.grid(column=3, row=0, padx=(15, 15))
        zipcode_frame.columnconfigure(0, weight=1)
        zipcode_frame.columnconfigure(1, weight=1)
        zipcode_frame.rowconfigure(0, weight=1)
        zipcode_frame.rowconfigure(1, weight=1)
        zipcode_frame.bind('<Visibility>', self._tab_switch)
        zipcode_label.grid(column=0, row=0, sticky=tkinter.E)
        zipcode_entry.grid(column=1, row=0, sticky=tkinter.W)
        zipcode_note_label.grid(column=0, row=1, columnspan=2, sticky=tkinter.N)
        latlon_frame.columnconfigure(0, weight=1)
        latlon_frame.columnconfigure(1, weight=1)
        latlon_frame.columnconfigure(2, weight=1)
        latlon_frame.columnconfigure(3, weight=1)
        latlon_frame.rowconfigure(0, weight=1)
        latlon_frame.rowconfigure(1, weight=1)
        latlon_frame.bind('<Visibility>', self._tab_switch)
        lat_label.grid(column=0, row=0, sticky=tkinter.E)
        lat_entry.grid(column=1, row=0, sticky=tkinter.W)
        lon_label.grid(column=2, row=0, sticky=tkinter.E)
        lon_entry.grid(column=3, row=0, sticky=tkinter.W)
        latlon_note_label.grid(column=0, row=1, columnspan=4, sticky=tkinter.N)
        latlon_note_label.bind(
            '<Button-1>',
            self._wrap_launch('https://www.gps-coordinates.net/my-location')
        )
        manual_frame.columnconfigure(0, weight=1)
        manual_frame.columnconfigure(1, weight=1)
        manual_frame.columnconfigure(2, weight=1)
        manual_frame.columnconfigure(3, weight=1)
        manual_frame.columnconfigure(4, weight=1)
        manual_frame.columnconfigure(5, weight=1)
        manual_frame.bind('<Visibility>', self._tab_switch)
        min_f_label.grid(column=0, row=0, sticky=tkinter.E)
        min_f_entry.grid(column=1, row=0, sticky=tkinter.W)
        avg_f_label.grid(column=2, row=0, sticky=tkinter.E)
        avg_f_entry.grid(column=3, row=0, sticky=tkinter.W)
        max_f_label.grid(column=4, row=0, sticky=tkinter.E)
        max_f_entry.grid(column=5, row=0, sticky=tkinter.W)
        sunrise_frame.grid(column=0, row=1, columnspan=3, sticky=tkinter.E, padx=(5, 5))
        sunrise_label.grid(column=0, row=0, sticky=tkinter.E)
        sunrise_hour_option.grid(column=1, row=0, sticky=tkinter.E)
        sunrise_colon_label.grid(column=2, row=0)
        sunrise_minute_option.grid(column=3, row=0, sticky=tkinter.W)
        sunset_frame.grid(column=3, row=1, columnspan=3, sticky=tkinter.W, padx=(5, 5))
        sunset_label.grid(column=0, row=0, sticky=tkinter.E)
        sunset_hour_option.grid(column=1, row=0, sticky=tkinter.E)
        sunset_colon_label.grid(column=2, row=0)
        sunset_minute_option.grid(column=3, row=0, sticky=tkinter.W)
        weather_state_frame.grid(column=0, row=2, columnspan=6)
        weather_state_entry_label.grid(column=0, row=0, sticky=tkinter.NSEW)
        weather_state_option.grid(column=1, row=0, sticky=tkinter.NSEW)

        middle_spacing_label.grid(column=0, row=2)
        for version in (1, 2, 3):
            self._image_containers[f'bt{version}_logo'].container.grid(
                column=0, row=2, columnspan=8
            )
            if self.config.version != version:
                self._image_containers[f'bt{version}_logo'].container.grid_remove()
        boktai_meter_frame.grid(column=0, row=3, columnspan=8)
        self._image_containers['bt1meter_bg'].container.grid(
            column=0, row=4, columnspan=8, sticky=tkinter.EW
        )
        self._image_containers['bt1meter_bg'].create_image(0, 0, anchor=tkinter.NW)
        self._image_containers['bt1meter_fg'].container.grid(
            column=0, row=4, columnspan=8, sticky=tkinter.EW
        )
        self._image_containers['bt1meter_fg'].create_image(0, 0, anchor=tkinter.NW)
        self._image_containers['bt1meter_fg'].container.grid_remove()
        if self.config.version != 1:
            self._image_containers['bt1meter_bg'].container.grid_remove()
        self._image_containers['bt2meter_bg'].container.grid(
            column=0, row=4, columnspan=8, sticky=tkinter.EW
        )
        self._image_containers['bt2meter_bg'].create_image(0, 0, anchor=tkinter.NW)
        self._image_containers['bt2meter_fg'].container.grid(
            column=0, row=4, columnspan=8, sticky=tkinter.EW
        )
        self._image_containers['bt2meter_fg'].create_image(0, 0, anchor=tkinter.NW)
        self._image_containers['bt2meter_fg'].container.grid_remove()
        if self.config.version != 2:
            self._image_containers['bt2meter_bg'].container.grid_remove()
        self._image_containers['bt3meter_bg'].container.grid(
            column=0, row=4, columnspan=8, sticky=tkinter.EW
        )
        self._image_containers['bt3meter_bg'].create_image(0, 0, anchor=tkinter.NW)
        self._image_containers['bt3meter_fg'].container.grid(
            column=0, row=4, columnspan=8, sticky=tkinter.EW
        )
        self._image_containers['bt3meter_fg'].create_image(0, 0, anchor=tkinter.NW)
        self._image_containers['bt3meter_fg'].container.grid_remove()
        if self.config.version != 3:
            self._image_containers['bt3meter_bg'].container.grid_remove()
        more_info_frame.grid(column=0, row=5, columnspan=8)
        location_label.grid(column=0, row=0, columnspan=5)
        min_temp_label.grid(column=0, row=1)
        current_temp_label.grid(column=1, row=1)
        max_temp_label.grid(column=2, row=1)
        weather_state_label.grid(column=0, row=2, columnspan=3)
        sun_state_label.grid(column=0, row=3, columnspan=3)

        options_frame.grid_columnconfigure(0, weight=1)
        ui_update_frame.grid(column=0, row=0, columnspan=2, padx=(10, 10))
        ui_update_timer_header.grid(column=0, row=0, columnspan=2)
        ui_update_timer_slider.grid(column=0, row=1)
        ui_update_timer_label.grid(column=1, row=1)
        ui_api_update_seperator.grid(column=0, row=1, columnspan=2, sticky=tkinter.EW, pady=(5, 5))
        api_update_frame.grid(column=0, row=2, columnspan=2, padx=(10, 10))
        api_update_timer_header.grid(column=0, row=0, columnspan=2)
        api_update_timer_slider.grid(column=0, row=1)
        api_update_timer_label.grid(column=1, row=1)
        api_update_mute_separator.grid(
            column=0, row=3, columnspan=2, sticky=tkinter.EW, pady=(5, 5)
        )
        mute_frame.grid(column=0, row=4, columnspan=2, padx=(10, 10))
        mute_flavor_checkbutton.grid(column=0, row=0, columnspan=2, padx=(5, 5))
        mute_alert_checkbutton.grid(column=2, row=0, columnspan=2, padx=(5, 5))
        alert_sound_label.grid(column=0, row=1, columnspan=2, sticky=tkinter.E)
        alert_sound_option.grid(column=2, row=1, columnspan=2, sticky=tkinter.W)
        mute_lunar_mode_separator.grid(
            column=0, row=5, columnspan=2, sticky=tkinter.EW, pady=(5, 5)
        )
        lunar_mode_checkbutton.grid(column=0, row=6, columnspan=2)
        lunar_mode_notes_label.grid(column=0, row=7, columnspan=2)
        lunar_mode_theme_separator.grid(
            column=0, row=8, columnspan=2, sticky=tkinter.EW, pady=(5, 5)
        )
        theme_picker_frame.grid(column=0, row=9, columnspan=2, padx=(10, 10))
        theme_label.grid(column=0, row=0)
        theme_option.grid(column=1, row=0)
        temp_scale_frame.grid(column=2, row=0, columnspan=2, padx=(10, 10))
        fahrenheit_radio.grid(column=0, row=0, sticky=tkinter.W)
        celsuis_radio.grid(column=1, row=0, sticky=tkinter.E)
        theme_logging_separator.grid(column=0, row=10, columnspan=2, sticky=tkinter.EW, pady=(5, 5))
        logging_level_frame.grid(column=0, row=11, columnspan=2, padx=(10, 10))
        logging_level_label.grid(column=0, row=0, sticky=tkinter.E)
        logging_level_option.grid(column=1, row=0, sticky=tkinter.W)

        logging_frame.columnconfigure(0, weight=1)
        logging_frame.rowconfigure(0, weight=1)
        logging_text.grid(column=0, row=0, sticky=tkinter.NSEW)
        logging_vertical_scroll.grid(column=1, row=0, sticky=tkinter.NS)
        logging_horizontal_scroll.grid(column=0, row=1, sticky=tkinter.EW)

        about_button.grid(column=0, row=1)
        bottom_frame.grid(column=0, row=2, sticky=tkinter.E)
        self._widget_dict = self.build_widget_dict(self.window)
        for _, widget in self._widget_dict.items():
            if isinstance(widget, tkinter.Entry):
                continue
            try:
                widget.configure(bg='#ECECEC', highlightbackground='#ECECEC')
            except tkinter.TclError:
                pass
        self.play_sound('open')
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        if self.config.area_type:
            if self.config.area_type == 'Zipcode':
                area_notebook.select(zipcode_frame)
            elif self.config.area_type == 'Lat/Lon':
                area_notebook.select(latlon_frame)
            elif self.config.area_type == 'Manual':
                area_notebook.select(manual_frame)
        self.window.mainloop()

    @staticmethod
    def build_widget_dict(
            tk_widget: Union[tkinter.BaseWidget, tkinter.Tk]
    ) -> Dict[str, tkinter.BaseWidget]:
        """ Recursively provides a dict of tkinter widgets, ignoring ones without explicit names """
        widget_dict = {}
        if not tk_widget.children:
            return {'.': tk_widget}
        for name, widget in tk_widget.children.items():
            if name.startswith('!'):
                continue
            if widget.children:
                inner_dict = WindowManager.build_widget_dict(widget)
                widget_dict[name] = widget
                widget_dict = {**widget_dict, **inner_dict}
                continue
            widget_dict[name] = widget
        return widget_dict

    def on_close(self, event: Optional[tkinter.Event] = None) -> None:
        if event:
            self.logger.debug(f'Received event {event}')
        self.logger.info('Quitting')
        self.play_sound('close')
        self.window.destroy()
        time.sleep(3)

    def do_update(self, event: Optional[tkinter.Event] = None) -> None:
        if event:
            self.logger.debug(f'Received event {event}')
        self.logger.debug('Performing update')
        if self._first_update:
            self._first_update = False
            self.timed_update()
            return
        self.config.version = int(self._widget_dict['version_combo'].get())
        if not 0 < self.config.version < 4:
            self.alert('warning', 'Boktai version must be between 1 and 3.')
            return
        update_logo = False
        if (self.boktaisim and self._last_version != self.version) or \
                (not self.boktaisim):
            update_logo = True
            self._last_version = self.version
        notebook = self._widget_dict['area_notebook']
        current_location_tab = notebook.tab(notebook.select(), "text")
        latlong = None
        manual_weather = None
        if current_location_tab == 'Zipcode':
            try:
                self.config.zipcode = int(
                    self._widget_dict['zipcode_entry'].get()
                )
            except ValueError:
                self.alert('warning', 'No zipcode provided.')
                return
            try:
                latlong = zip_to_latlong(self.config.zipcode)
            except KeyError:
                self.alert('warning', 'Invalid zipcode provided.')
                return
        elif current_location_tab == 'Lat/Lon':
            try:
                float(self._widget_dict['lat_entry'].get())
                float(self._widget_dict['lon_entry'].get())
            except ValueError:
                self.alert('warning', 'Invalid latitude and longitude provided.')
                return
            self.config.lat = self._widget_dict['lat_entry'].get()
            self.config.lon = self._widget_dict['lon_entry'].get()
            latlong = f'{self.config.lat},{self.config.lon}'
        elif current_location_tab == 'Manual':
            if not (self._widget_dict['min_f_entry'].get() and
                    self._widget_dict['avg_f_entry'].get() and
                    self._widget_dict['max_f_entry'].get()):
                self.alert('warning', 'All fields must be filled when in Manual mode!')
                return
            if self.config.temp_scale == 'C':
                try:
                    self.config.min_f = c_to_f(self._widget_dict['min_f_entry'].get())
                    self.config.avg_f = c_to_f(self._widget_dict['avg_f_entry'].get())
                    self.config.max_f = c_to_f(self._widget_dict['max_f_entry'].get())
                except ValueError:
                    self.alert('warning',
                               'Temperature range values must be whole or decimal numbers.')
                    return
            else:
                try:
                    self.config.min_f = float(self._widget_dict['min_f_entry'].get())
                    self.config.avg_f = float(self._widget_dict['avg_f_entry'].get())
                    self.config.max_f = float(self._widget_dict['max_f_entry'].get())
                except ValueError:
                    self.alert('warning',
                               'Temperature range values must be whole or decimal numbers.')
                    return
            if not self.config.min_f <= self.config.avg_f <= self.config.max_f:
                self.alert('warning', 'Temperature values do not make sense!')
                return
            try:
                self.config.weather = \
                    WEATHER_STATES_REVERSE[self._tk_variables['weather_state_option'].get()]
            except KeyError:
                self.alert('warning', 'Invalid weather state provided.')
                return
            try:
                sunrise_hour = int(self._tk_variables['sunrise_hour_option'].get())
                sunrise_minute = int(self._tk_variables['sunrise_minute_option'].get())
                sunset_hour = int(self._tk_variables['sunset_hour_option'].get())
                sunset_minute = int(self._tk_variables['sunset_minute_option'].get())
            except ValueError:
                self.alert('warning', 'Invalid time provided')
                return
            self.config.sunrise = f'{sunrise_hour}:{sunrise_minute}'
            self.config.sunset = f'{sunset_hour}:{sunset_minute}'
            current_datetime = datetime.datetime.now(tz=LOCAL_TIMEZONE)
            sunrise_datetime = current_datetime.replace(hour=sunrise_hour, minute=sunrise_minute)
            sunset_datetime = current_datetime.replace(hour=sunset_hour, minute=sunset_minute)
            if sunset_datetime < sunrise_datetime:
                self.alert('warning', 'Sunset must come after sunrise.')
                return
            latlong = 'manual'
            city = 'Noplace'
            if self.config.version == 1:
                city = 'Istrakan'
            elif self.config.version == 2 or self.config.version == 3:
                city = 'San Miguel'

            min_temp_val = round(f_to_c(self.config.min_f), 2)
            avg_temp_val = round(f_to_c(self.config.avg_f), 2)
            max_temp_val = round(f_to_c(self.config.max_f), 2)
            current_temp_val = round(f_to_c(self.config.avg_f), 2)

            manual_weather = WeatherInfo(
                state='World of Boktai',
                city=city,
                latlong=latlong,
                woeid='0',
                min_temp=min_temp_val,
                max_temp=max_temp_val,
                current_temp=current_temp_val,
                visibility=0,
                weather_state=self.config.weather,
                sunrise=sunrise_datetime.strftime('%Y-%m-%dT%H:%M:%S.%f%z'),
                sunset=sunset_datetime.strftime('%Y-%m-%dT%H:%M:%S.%f%z'),
                timestamp=current_datetime.strftime('%Y-%m-%dT%H:%M:%S.%f%Z'),
                avg_temp=avg_temp_val,
                manual=True
            )
            self.boktaisim = BoktaiSim(manual_data=manual_weather, parent=self)

        if latlong not in self._sim_dict and current_location_tab != 'Manual':
            if current_location_tab == 'Zipcode':
                try:
                    self.boktaisim = BoktaiSim(zipcode=self.config.zipcode, parent=self)
                except KeyError:
                    self.alert('warning', 'Invalid zipcode provided.')
                    return
                except requests.ConnectionError as e:
                    self.alert(
                        'Warning',
                        'Can not connect to API! Only manual mode is available.\n'
                        'More info:\n\n'
                        f'{e}'
                    )
                    return
            elif current_location_tab == 'Lat/Lon' and current_location_tab != 'Manual':
                try:
                    self.boktaisim = BoktaiSim(latlon=latlong, parent=self)
                except requests.ConnectionError as e:
                    self.alert(
                        'warning',
                        'Can not connect to API! Only manual mode is available.\n'
                        'More info:\n\n'
                        f'{e}'
                    )
                    return
            self._sim_dict[latlong] = self.boktaisim
        elif current_location_tab == 'Manual':
            self.boktaisim = BoktaiSim(manual_data=manual_weather, parent=self)
            self._sim_dict[latlong] = self.boktaisim
        else:
            self.boktaisim = self._sim_dict[latlong]
            if self.boktaisim.weather.data_age() > self.config.api_update_interval:
                try:
                    self.boktaisim.weather.update()
                except Exception as e:
                    self.alert(
                        'warning',
                        'Can not connect to API! Only manual mode is available.\n'
                        'More info:\n\n'
                        f'{e}'
                    )
                    return
        self._widget_dict['location_label'].configure(
            text=f'{self.boktaisim.weather.city}, {self.boktaisim.weather.state}'
        )
        if self.config.temp_scale == 'C':
            self._widget_dict['min_temp_label'].configure(
                text=f'Min °C: {self.boktaisim.weather.min_temp}'
            )
            self._widget_dict['current_temp_label'].configure(
                text=f'Current °C: {self.boktaisim.weather.current_temp}'
            )
            self._widget_dict['max_temp_label'].configure(
                text=f'Max °C: {self.boktaisim.weather.max_temp}'
            )
            self._widget_dict['min_f_label'].configure(
                text=f'Min °C: '
            )
            self._widget_dict['avg_f_label'].configure(
                text=f'Avg °C: '
            )
            self._widget_dict['max_f_label'].configure(
                text=f'Max °C: '
            )
        else:
            self._widget_dict['min_temp_label'].configure(
                text=f'Min °F: {self.boktaisim.weather.min_temp_f}'
            )
            self._widget_dict['current_temp_label'].configure(
                text=f'Current °F: {self.boktaisim.weather.current_temp_f}'
            )
            self._widget_dict['max_temp_label'].configure(
                text=f'Max °F: {self.boktaisim.weather.max_temp_f}'
            )
            self._widget_dict['min_f_label'].configure(
                text=f'Min °F: '
            )
            self._widget_dict['avg_f_label'].configure(
                text=f'Avg °F: '
            )
            self._widget_dict['max_f_label'].configure(
                text=f'Max °F: '
            )
        weather_image = tkinter.PhotoImage(
            file=self._imgs[f'{self.boktaisim.weather.weather_state}.gif']
        )
        self._widget_dict['weather_state_label'].configure(
            text=f'Current Weather: {WEATHER_STATES[self.boktaisim.weather.weather_state]["name"]}',
            image=weather_image
        )
        self._widget_dict['weather_state_label'].image = weather_image
        sun_image = tkinter.PhotoImage(
            file=self._imgs[f'{self.boktaisim.weather.sun_state}.gif']
        )
        self._widget_dict['sun_state_label'].configure(
            text=f'Sun Status: {self.boktaisim.weather.sun_state}',
            image=sun_image
        )
        self._widget_dict['sun_state_label'].image = sun_image
        if update_logo:
            for i in [1, 2, 3]:
                self._widget_dict[f'boktai{i}_logo'].grid_remove()
                self._widget_dict[f'boktai{i}_meter_bg'].grid_remove()
                self._widget_dict[f'boktai{i}_meter_fg'].grid_remove()
            self._widget_dict[f'boktai{self.config.version}_logo'].grid(
                column=0, row=2, columnspan=8
            )
            self._widget_dict[f'boktai{self.config.version}_meter_bg'].grid(
                column=0, row=4, columnspan=4, padx=45, sticky=tkinter.W
            )
            self._widget_dict[f'boktai{self.config.version}_meter_fg'].grid(
                column=0, row=4, columnspan=4, padx=45, sticky=tkinter.W
            )
        self._update_bar(True)
        self._update_logo()
        self.config.save()

    def alert(self, level: str, msg: str) -> None:
        self.play_sound(level)
        messagebox.showwarning(level, msg)
        self.logger.log(logging.getLevelName(level.upper()), msg)

    def timed_update(self) -> None:
        self.logger.info('Performing timed update')
        self.do_update()
        self.window.after(self.config.gui_update_interval * 1000, self.timed_update)

    def play_sound(self, sound: str) -> None:
        if sound not in self._sound_dict:
            return
        if self.config.mute_alert_sounds and self._sound_dict[sound]['type'] == 'alert':
            return
        if self.config.mute_flavor_sounds and self._sound_dict[sound]['type'] == 'flavor':
            return
        if self._sound_dict[sound]['segment']:
            logging.debug(f'Playing sound `{sound}`')
            self._sound_dict[sound]['segment'].play()

    def about_window(self) -> None:
        about_window = tkinter.Toplevel(self.window)
        about_window.resizable(False, False)
        about_window.configure(bg='#ECECEC')
        about_window.title('About boktaisim')
        title_label = tkinter.Label(
            about_window, text='Solar Sensor Simulator\nfor the\nBoktai Trilogy',
            bg='#ECECEC', highlightbackground='#ECECEC', font=("TkDefaultFont", 24, "bold")
        )
        otenko_img = tkinter.PhotoImage(file=self._imgs["Solar_Sensor_Icon.gif"])
        otenko_logo = tkinter.Label(
            about_window, image=otenko_img, bg='#ECECEC', highlightbackground='#ECECEC',
            name='otenko_logo'
        )
        version_label = tkinter.Label(
            about_window, text=f'Version {__version__}', fg="gray33", font=("TkDefaultFont", 10),
            bg='#ECECEC', highlightbackground='#ECECEC'
        )
        more_info_frame = tkinter.Frame(about_window, border=3, relief='ridge')
        credits_idea_pre = tkinter.Label(more_info_frame, text='Idea by Nathan Stiles of')
        credits_idea_post = tkinter.Label(
            more_info_frame, text=f'Stiles\' Reviews', fg="blue", cursor=self._link_cursor
        )
        credits_coding_pre = tkinter.Label(more_info_frame, text='Original code by')
        credits_coding_post = tkinter.Label(
            more_info_frame, text='Connor Barthold', fg='blue', cursor=self._link_cursor
        )
        credits_api_pre = tkinter.Label(more_info_frame, text='Uses the free')
        credits_api_post = tkinter.Label(
            more_info_frame, text='MetaWeather API', fg='blue', cursor=self._link_cursor
        )

        close_button = tkinter.ttk.Button(
            about_window,
            text='Close',
            style="custom.TButton",
            command=about_window.destroy,
            name="close_button"
        )

        title_label.grid(row=0, column=0)
        otenko_logo.grid(row=1, column=0)
        version_label.grid(row=2, column=0)
        more_info_frame.grid(row=3, column=0)
        credits_idea_pre.grid(row=0, column=0, sticky=tkinter.E)
        credits_idea_post.grid(row=0, column=1, sticky=tkinter.W)
        credits_idea_post.bind(
            '<Button-1>',
            self._wrap_launch('https://www.youtube.com/c/StilesReviews')
        )
        credits_coding_pre.grid(row=1, column=0, sticky=tkinter.E)
        credits_coding_post.grid(row=1, column=1, sticky=tkinter.W)
        credits_coding_post.bind(
            '<Button-1>',
            self._wrap_launch('https://keybase.io/conchobar')
        )
        credits_api_pre.grid(row=2, column=0, sticky=tkinter.E)
        credits_api_post.grid(row=2, column=1, sticky=tkinter.W)
        credits_api_post.bind(
            '<Button-1>',
            self._wrap_launch('https://www.metaweather.com/')
        )
        close_button.grid(row=4, column=0)
        self.play_sound('about')
        about_window.mainloop()

    @staticmethod
    def _wrap_launch(url: str):
        def _launch_browser(event: Optional[tkinter.Event] = None):
            if event:
                logging.debug(f'Received event {event}')
            webbrowser.open(url=url)
        return _launch_browser

    def _wrap_option(self, widget_label: str, option_label: Optional[str] = None):
        def _option_setter(event: Optional[tkinter.Event] = None):
            if event:
                logging.debug(f'Received event {event}')
            if option_label:
                value = self._tk_variables[option_label].get()
            else:
                value = self._tk_variables[widget_label].get()
            if isinstance(self._widget_dict[widget_label], tkinter.ttk.Checkbutton):
                if value == 0:
                    self.config.__dict__[widget_label] = False
                else:
                    self.config.__dict__[widget_label] = True
            elif isinstance(self._widget_dict[widget_label], tkinter.Scale):
                self.config.__dict__[widget_label] = value * 60
            elif isinstance(self._widget_dict[widget_label], tkinter.ttk.Radiobutton) and \
                    option_label:
                self.config.__dict__[option_label] = value
            else:
                self.config.__dict__[widget_label] = self._widget_dict[widget_label].get()
            self.config.save()
        return _option_setter

    def _update_bar(self, update_value: bool = False) -> None:
        self._image_containers[f'bt{self.version}meter_bg'].container.configure(
            width=self._canvas_width
        )
        win_height = self.window.winfo_height()
        if self.version == 1:
            size_height = round(270 * win_height / 100) // 5
            size_width = round(51 * win_height / 100) // 5
        else:
            size_height = round(280 * win_height / 100) // 5
            size_width = round(47 * win_height / 100) // 5
        if size_height == 0:
            return
        self._image_containers[f'bt{self.version}meter_bg'].image = \
            self._image_containers[f'bt{self.version}meter_bg'].image_copy.resize(
                (size_height, size_width)
            )
        self._image_containers[f'bt{self.version}meter_bg'].tkimage = \
            ImageTk.PhotoImage(self._image_containers[f'bt{self.version}meter_bg'].image)
        self._image_containers[f'bt{self.version}meter_bg'].container.itemconfigure(
            self._image_containers[f'bt{self.version}meter_bg'].created_image,
            image=self._image_containers[f'bt{self.version}meter_bg'].tkimage
        )
        self._image_containers[f'bt{self.version}meter_bg'].container.configure(
            width=size_height, height=size_width
        )

        if update_value:
            try:
                bar_value = self.boktaisim.value
            except AttributeError:
                return
            if self._last_value != bar_value:
                self.play_sound('bar_update')
            self._last_value = bar_value
        else:
            if not self.boktaisim:
                return
            bar_value = self._last_value
        canvas_width = round(BOKTAI_METER[self.version][bar_value] * win_height / 100) // 5
        if self.version == 1:
            size_width = round(51 * win_height / 100) // 5
        else:
            size_width = round(47 * win_height / 100) // 5
        self._image_containers[f'bt{self.version}meter_fg'].image = \
            self._image_containers[f'bt{self.version}meter_fg'].image_copy.resize(
                (size_height, size_width)
            )
        self._image_containers[f'bt{self.version}meter_fg'].tkimage = ImageTk.PhotoImage(
            self._image_containers[f'bt{self.version}meter_fg'].image
        )
        self._image_containers[f'bt{self.version}meter_fg'].container.itemconfigure(
            self._image_containers[f'bt{self.version}meter_fg'].created_image,
            image=self._image_containers[f'bt{self.version}meter_fg'].tkimage
        )
        self._image_containers[f'bt{self.version}meter_fg'].container.configure(
            width=canvas_width, height=size_width
        )

    def _update_logo(self) -> None:
        win_height = self.window.winfo_height()
        size_height = round(250 * win_height / 100) // 5
        size_width = round(90 * win_height / 100) // 5
        if size_height == 0:
            return
        self._image_containers[f'bt{self.version}_logo'].image = \
            self._image_containers[f'bt{self.version}_logo'].image_copy.resize(
                (size_height, size_width)
            )
        self._image_containers[f'bt{self.version}_logo'].tkimage = \
            ImageTk.PhotoImage(self._image_containers[f'bt{self.version}_logo'].image)
        self._image_containers[f'bt{self.version}_logo'].container.configure(
            image=self._image_containers[f'bt{self.version}_logo'].tkimage
        )

    def _resize_window(self, event=None) -> None:
        if isinstance(event.widget, tkinter.Tk):
            if self._last_win_size == f'{event.width}x{event.height}':
                return
            self._last_win_size = f'{event.width}x{event.height}'
            self._update_bar()
            self._update_logo()
            win_height = event.height
            win_width = event.width
            main_font_height = round(3 * win_height / 100)
            caption_font_height = round(2 * win_height / 100)
            self._main_font['size'] = main_font_height
            self._caption_font['size'] = caption_font_height
            for label, widget in self._widget_dict.items():
                if (
                        isinstance(widget, tkinter.Label) or
                        isinstance(widget, tkinter.Scale) or
                        isinstance(widget, tkinter.Radiobutton) or
                        isinstance(widget, tkinter.Entry)
                ) and widget.cget('font') in ['TkDefaultFont', 'TkTextFont', 'font1']:
                    widget.configure(font=self._main_font)
                if isinstance(widget, tkinter.Label) and \
                        widget.cget('font') == 'TkSmallCaptionFont':
                    widget.configure(font=self._caption_font)
                if isinstance(widget, tkinter.Scale):
                    length = round(40 * win_width / 100)
                    widget.configure(length=length)
                if isinstance(widget, tkinter.ttk.Button):
                    style = tkinter.ttk.Style()
                    style.configure(
                        'custom.TButton',
                        font=('TkDefaultFont', main_font_height)
                    )
                if isinstance(widget, tkinter.ttk.Radiobutton):
                    style = tkinter.ttk.Style()
                    style.configure(
                        'custom.TRadiobutton',
                        font=('TkDefaultFont', main_font_height)
                    )
                if isinstance(widget, tkinter.ttk.Checkbutton):
                    style = tkinter.ttk.Style()
                    style.configure(
                        'custom.TCheckbutton',
                        font=('TkDefaultFont', main_font_height)
                    )
                if isinstance(widget, tkinter.ttk.Combobox):
                    style = tkinter.ttk.Style()
                    style.configure(
                        'custom.TCombobox',
                        font=('TkDefaultFont', main_font_height)
                    )
                if isinstance(widget, tkinter.ttk.Notebook):
                    style = tkinter.ttk.Style()
                    style.configure(
                        'custom.TNotebook.Tab',
                        font=('TkDefaultFont', main_font_height)
                    )
                    style = tkinter.ttk.Style()
                    style.configure(
                        'centered.TNotebook.Tab',
                        font=('TkDefaultFont', main_font_height)
                    )
                    style.configure(
                        'centered.TNotebook',
                        tabposition='n'
                    )

    def _tab_switch(self, event: Optional[tkinter.Event] = None) -> None:
        if event:
            self.logger.debug(f'Received event {event}')
        area_notebook = self._widget_dict['area_notebook']
        self.config.area_type = area_notebook.tab(area_notebook.select(), 'text')
        self.config.save()

    def _update_temp_scale(self, event: Optional[tkinter.Event] = None) -> None:
        if event:
            self.logger.debug(f'Received event {event}')
        if self.config.temp_scale != self._tk_variables['temp_scale'].get():
            if not self.boktaisim:
                return
            self.config.temp_scale = self._tk_variables['temp_scale'].get()
            if self.config.temp_scale == 'C':
                self._widget_dict['min_temp_label'].configure(
                    text=f'Min °C: {self.boktaisim.weather.min_temp}'
                )
                self._widget_dict['current_temp_label'].configure(
                    text=f'Current °C: {self.boktaisim.weather.current_temp}'
                )
                self._widget_dict['max_temp_label'].configure(
                    text=f'Max °C: {self.boktaisim.weather.max_temp}'
                )
                self._widget_dict['min_f_label'].configure(
                    text=f'Min °C: '
                )
                self._widget_dict['avg_f_label'].configure(
                    text=f'Avg °C: '
                )
                self._widget_dict['max_f_label'].configure(
                    text=f'Max °C: '
                )
            else:
                self._widget_dict['min_temp_label'].configure(
                    text=f'Min °F: {self.boktaisim.weather.min_temp_f}'
                )
                self._widget_dict['current_temp_label'].configure(
                    text=f'Current °F: {self.boktaisim.weather.current_temp_f}'
                )
                self._widget_dict['max_temp_label'].configure(
                    text=f'Max °F: {self.boktaisim.weather.max_temp_f}'
                )
                self._widget_dict['min_f_label'].configure(
                    text=f'Min °F: '
                )
                self._widget_dict['avg_f_label'].configure(
                    text=f'Avg °F: '
                )
                self._widget_dict['max_f_label'].configure(
                    text=f'Max °F: '
                )
            if self.config.temp_scale == 'F':
                if self._widget_dict['min_f_entry'].get():
                    min_f = round(c_to_f(self._widget_dict['min_f_entry'].get()), 2)
                    self._widget_dict['min_f_entry'].delete(0, tkinter.END)
                    self._widget_dict['min_f_entry'].insert(
                        0, min_f
                    )
                if self._widget_dict['avg_f_entry'].get():
                    avg_f = round(c_to_f(self._widget_dict['avg_f_entry'].get()), 2)
                    self._widget_dict['avg_f_entry'].delete(0, tkinter.END)
                    self._widget_dict['avg_f_entry'].insert(
                        0, avg_f
                    )
                if self._widget_dict['max_f_entry'].get():
                    max_f = round(c_to_f(self._widget_dict['max_f_entry'].get()), 2)
                    self._widget_dict['max_f_entry'].delete(0, tkinter.END)
                    self._widget_dict['max_f_entry'].insert(
                        0, max_f
                    )
            if self.config.temp_scale == 'C':
                if self._widget_dict['min_f_entry'].get():
                    min_f = round(f_to_c(self._widget_dict['min_f_entry'].get()), 2)
                    self._widget_dict['min_f_entry'].delete(0, tkinter.END)
                    self._widget_dict['min_f_entry'].insert(
                        0, min_f
                    )
                if self._widget_dict['avg_f_entry'].get():
                    avg_f = round(f_to_c(self._widget_dict['avg_f_entry'].get()), 2)
                    self._widget_dict['avg_f_entry'].delete(0, tkinter.END)
                    self._widget_dict['avg_f_entry'].insert(
                        0, avg_f
                    )
                if self._widget_dict['max_f_entry'].get():
                    max_f = round(f_to_c(self._widget_dict['max_f_entry'].get()), 2)
                    self._widget_dict['max_f_entry'].delete(0, tkinter.END)
                    self._widget_dict['max_f_entry'].insert(
                        0, max_f
                    )

    def _update_theme(self, event: Optional[tkinter.Event] = None) -> None:
        if event:
            self.logger.debug(f'Received event {event}')
        tkinter.ttk.Style().theme_use(self._tk_variables['theme'].get())
        self.config.theme = self._tk_variables['theme'].get()
        self.logger.debug(f'Updating theme to `{self.config.theme}`')
        self.config.save()

    def _update_logging_level(self, event: Optional[tkinter.Event] = None) -> None:
        if event:
            self.logger.debug(f'Received event {event}')
        logging_level = self._tk_variables['logging_level'].get()
        if logging_level != self.config.logging_level:
            self.logger.debug(f'Setting log level to `{logging_level}`')
            self.logger.setLevel(logging.getLevelName(logging_level))
        self.logger.info(f'Updating theme to `{self.config.theme}`')
        self.config.logging_level = logging_level
        self.config.save()

    def _set_alert_sound(self, event: Optional[tkinter.Event] = None) -> None:
        if event:
            self.logger.debug(f'Received event {event}')
        selection = self._tk_variables["alert_sound_option"].get()
        if sys.platform == 'win32' and hasattr(sys, 'frozen'):
            audio_segment = simpleaudio.WaveObject.from_wave_file(f'resources/{selection}.wav')
            self._sound_dict['bar_update']['segment'] = audio_segment
            self._sound_dict['bar_update']['file'] = f'resources/{selection}.wav'
        else:
            with pkg_resources.path('boktaisim.resources', f'{selection}.wav') as sound_path:
                audio_segment = simpleaudio.WaveObject.from_wave_file(str(sound_path))
                self._sound_dict['bar_update']['segment'] = audio_segment
                self._sound_dict['bar_update']['file'] = f'{selection}.wav'
        self.play_sound('bar_update')
        self.config.alert_sound_option = selection
        self.config.save()

    @property
    def min_temp(self) -> Optional[float]:
        if self.boktaisim:
            return self.boktaisim.weather.min_temp_f
        return None

    @property
    def max_temp(self) -> Optional[float]:
        if self.boktaisim:
            return self.boktaisim.weather.max_temp_f
        return None

    @property
    def current_temp(self) -> Optional[float]:
        if self.boktaisim:
            return self.boktaisim.weather.current_temp_f
        return None

    @property
    def version(self) -> int:
        return self.config.version

    @version.setter
    def version(self, value):
        assert isinstance(value, int)
        self.config.version = value

    @property
    def lunar_mode(self) -> bool:
        return self.config.lunar_mode

    @lunar_mode.setter
    def lunar_mode(self, value: bool) -> None:
        self.config.lunar_mode = value


class ImageHandler(object):
    def __init__(
            self,
            image: Image,
            image_copy: Image,
            tkimage: ImageTk.PhotoImage,
            container: Union[tkinter.Label, tkinter.Canvas],
            name: str,
            version: int
    ) -> None:
        self.image = image
        self.image_copy = image_copy
        self.tkimage = tkimage
        self.container = container
        self.created_image = None
        self.name = name
        self.version = version

    @classmethod
    def from_file(
            cls,
            file_path: str,
            version: int,
            parent: tkinter.BaseWidget,
            container_type: str,
            name: str,
            *args,
            **kwargs
    ):
        image = Image.open(file_path)
        image_copy = image.copy()
        tkimage = ImageTk.PhotoImage(image)
        if container_type == 'Canvas':
            container = tkinter.Canvas(
                parent, *args, bg='#ECECEC', highlightbackground='#ECECEC', borderwidth=0,
                highlightthickness=0, name=name, **kwargs
            )
        elif container_type == 'Label':
            container = tkinter.Label(
                parent, *args, bg='#ECECEC', highlightbackground='#ECECEC', borderwidth=0,
                highlightthickness=0, name=name, **kwargs
            )
        else:
            raise ValueError('container_type must be either Canvas or Label')
        return cls(
            image=image,
            image_copy=image_copy,
            tkimage=tkimage,
            container=container,
            name=name,
            version=version
        )

    @property
    def container_type(self) -> str:
        return self.container.__class__.__name__

    def create_image(self, *args, **kwargs) -> int:
        self.created_image = self.container.create_image(*args, image=self.tkimage, **kwargs)
        return self.created_image


class TextHandler(logging.Handler):
    """This class allows you to log to a Tkinter Text or ScrolledText widget"""

    def __init__(self, text) -> None:
        # run the regular Handler __init__
        logging.Handler.__init__(self)
        # Store a reference to the Text it will log to
        self.text = text

    def emit(self, record) -> None:
        msg = self.format(record)

        def append():
            self.text.configure(state='normal')
            tag = 'INFO'
            if 'DEBUG' in msg:
                tag = 'DEBUG'
            if 'WARNING' in msg:
                tag = 'WARNING'
            if 'ERROR' in msg:
                tag = 'ERROR'
            if 'CRITICAL' in msg:
                tag = 'CRITICAL'
            self.text.insert(tkinter.END, msg + '\n', tag)
            self.text.configure(state='disabled')
            # Autoscroll to the bottom
            self.text.yview(tkinter.END)
        # This is necessary because we can't modify the Text from other threads
        self.text.after(0, append)
