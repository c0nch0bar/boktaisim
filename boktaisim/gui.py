#!/usr/bin/env python
# -*- coding: utf-8 -*-

import simpleaudio
import importlib.resources as pkg_resources
import platform
import requests
import datetime
import multiprocessing
import sys
import tkinter
from tkinter import messagebox, scrolledtext
import tkinter.ttk
import webbrowser
import logging

from typing import Dict, Optional, Union

from .classes import BoktaiSim, BoktaiConfig, zip_to_latlong, check_latlong, WeatherInfo,\
    c_to_f, f_to_c
from .constants import BOKTAI_METER, IMAGES, SOUNDS, SUN_STATES, WEATHER_STATES,\
    WEATHER_STATES_REVERSE, LOCAL_TIMEZONE
from .version import __version__


class WindowManager(object):
    def __init__(
            self,
            config_file: Optional[str] = None
    ):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.window = tkinter.Tk()
        self.boktaisim: Optional[BoktaiSim] = None
        self.config = BoktaiConfig.from_json(config_file)
        self._current_theme = None
        self._last_value = None
        self._last_version = None
        self._last_temp_scale = None
        self._first_update = True
        self._tk_variables = {}
        self._sim_dict = {}
        self._sound_dict = {}
        self._widget_dict = {}
        self._imgs = {}
        self._pil_imgs = {}
        self._init_image_paths()
        self._init_sound_dict()
        self._set_icon()

    def _init_sound_dict(self) -> None:
        self._sound_dict = SOUNDS.copy()
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
            elif sys.platform == 'win32':
                pass
            else:
                with pkg_resources.path('boktaisim.resources', image_name) as image_path:
                    self._imgs[image_name] = image_path
            continue

    def _set_icon(self) -> None:
        system = platform.system()
        if system == 'Windows':
            # self.window.iconbitmap(self._imgs["boktaisim_icon.ico"])
            pass
        elif system == 'Darwin':
            # Looks like there's no actual way to set an icon on Mac with tkinter :'(
            # self.window.iconbitmap(self._imgs["boktaisim_icon.gif"])
            pass
        else:
            self.window.iconbitmap(self._imgs["boktaisim_icon.gif.xbm"])

    def main(self, pipe: Optional[multiprocessing.Pipe] = None) -> None:
        self.window.geometry('400x475')
        self.window.minsize(400, 475)
        self.window.maxsize()
        style = tkinter.ttk.Style(self.window)
        # style.theme_create("boktai", settings={})
        hours = list(range(0, 25))
        minutes = list(range(0, 60))

        style.theme_use("classic")
        self.window.configure(bg='#ECECEC')
        tkinter.ttk.Style().configure('custom.TButton', foreground='black', background='#ECECEC')
        tkinter.ttk.Style().configure('bottomtab.TNotebook', tabposition='s')
        tkinter.ttk.Style().configure('centered.TNotebook', tabposition='n')

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
        master_notebook = tkinter.ttk.Notebook(self.window, name='master_notebook')
        simulator_frame = tkinter.Frame(master_notebook, name='simulator_frame')
        options_frame = tkinter.Frame(master_notebook, padx=10, pady=10, name='options_frame')
        logging_frame = tkinter.Frame(master_notebook, name='logging_frame')
        logging_text = scrolledtext.ScrolledText(
            logging_frame, state='disabled', font='TkFixedFont', name='logging_text'
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
        boktai1_img = tkinter.PhotoImage(file=self._imgs["boktai1_logo.gif"])
        boktai1_logo = tkinter.Label(
            simulator_frame, image=boktai1_img, bg='#ECECEC', highlightbackground='#ECECEC',
            name='boktai1_logo'
        )
        boktai_2_img = tkinter.PhotoImage(file=self._imgs["boktai2_logo.gif"])
        boktai_2_logo = tkinter.Label(
            simulator_frame, image=boktai_2_img, bg='#ECECEC', highlightbackground='#ECECEC',
            name='boktai2_logo'
        )
        boktai_3_img = tkinter.PhotoImage(file=self._imgs["boktai3_logo.gif"])
        boktai_3_logo = tkinter.Label(
            simulator_frame, image=boktai_3_img, bg='#ECECEC', highlightbackground='#ECECEC',
            name='boktai3_logo'
        )
        area_notebook = tkinter.ttk.Notebook(
            simulator_frame, name='area_notebook', style='centered.TNotebook'
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
            version_and_submit_frame,  width=2, name='version_combo'
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
            font=("TkDefaultFont", 12, "italic"), name='zipcode_note_label'
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
            fg="blue", cursor="hand", name='latlon_note_label'
        )
        if self.config.lon:
            lon_entry.insert(0, self.config.lon)
        min_f_label = tkinter.Label(
            manual_frame, text=f'Min °{self.config.temp_scale}: ', name='min_f_label'
        )
        if self.config.temp_scale == 'C':
            min_f = round(f_to_c(self.config.min_f), 2)
            avg_f = round(f_to_c(self.config.avg_f), 2)
            max_f = round(f_to_c(self.config.max_f), 2)
        else:
            min_f = self.config.min_f
            avg_f = self.config.avg_f
            max_f = self.config.max_f
        min_f_entry = tkinter.Entry(manual_frame, width=4, name='min_f_entry')
        if self.config.min_f:
            min_f_entry.insert(0, min_f)
        avg_f_label = tkinter.Label(
            manual_frame, text=f'Avg °{self.config.temp_scale}: ', name='avg_f_label'
        )
        avg_f_entry = tkinter.Entry(manual_frame, width=4, name='avg_f_entry')
        if self.config.avg_f:
            avg_f_entry.insert(0, avg_f)
        max_f_label = tkinter.Label(
            manual_frame, text=f'Max °{self.config.temp_scale}: ', name='max_f_label'
        )
        max_f_entry = tkinter.Entry(manual_frame, width=4, name='max_f_entry')
        if self.config.max_f:
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
            more_info_frame, text=f'Max °{self.config.temp_scale}: ??',name='max_temp_label'
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
        boktai1_meter_bg_img = tkinter.PhotoImage(
            file=self._imgs["boktai1_meter_empty.gif"]
        )
        boktai1_meter_bg = tkinter.Label(
            boktai_meter_frame, width=270, height=51, image=boktai1_meter_bg_img,
            bg='#ECECEC', highlightbackground='#ECECEC', name="boktai1_meter_bg"
        )
        boktai2_meter_bg_img = tkinter.PhotoImage(
            file=self._imgs["boktai2_meter_empty.gif"]
        )
        boktai2_meter_bg = tkinter.Label(
            boktai_meter_frame, width=280, height=51, image=boktai2_meter_bg_img,
            bg='#ECECEC', highlightbackground='#ECECEC', name="boktai2_meter_bg"
        )
        boktai3_meter_bg_img = tkinter.PhotoImage(
            file=self._imgs["boktai3_meter_empty.gif"]
        )
        boktai3_meter_bg = tkinter.Label(
            boktai_meter_frame, width=280, height=51, image=boktai3_meter_bg_img,
            bg='#ECECEC', highlightbackground='#ECECEC', name="boktai3_meter_bg"
        )
        boktai1_meter_fg_img = tkinter.PhotoImage(
            file=self._imgs["boktai1_meter_full.gif"]
        )
        boktai1_meter_fg = tkinter.Label(
            boktai_meter_frame, width=0, height=51, image=boktai1_meter_fg_img,
            bg='#ECECEC', highlightbackground='#ECECEC', name="boktai1_meter_fg"
        )
        boktai2_meter_fg_img = tkinter.PhotoImage(
            file=self._imgs["boktai2_meter_full.gif"]
        )
        boktai2_meter_fg = tkinter.Label(
            boktai_meter_frame, width=0, height=51, image=boktai2_meter_fg_img,
            bg='#ECECEC', highlightbackground='#ECECEC', name="boktai2_meter_fg"
        )
        boktai3_meter_fg_img = tkinter.PhotoImage(
            file=self._imgs["boktai3_meter_full.gif"]
        )
        boktai3_meter_fg = tkinter.Label(
            boktai_meter_frame, width=0, height=51, image=boktai3_meter_fg_img,
            bg='#ECECEC', highlightbackground='#ECECEC', name="boktai3_meter_fg"
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
            name='lunar_mode'
        )
        lunar_mode_notes_label = tkinter.Label(
            options_frame, text='*Boktai is not meant to be played at night and by default this \n'
                                'program reflects that. This setting uses lower readings based \n'
                                'off of weather, excluding sunlight.',
            font=("TkDefaultFont", 12, "italic"),
            name='lunar_mode_notes_label'
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
            name='fahrenheit_radio'
        )
        celsuis_radio = tkinter.ttk.Radiobutton(
            temp_scale_frame,
            text='Celsius',
            command=self._update_temp_scale,
            variable=self._tk_variables['temp_scale'],
            value='C',
            name='celsuis_radio'
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
        zipcode_label.grid(column=0, row=0, sticky=tkinter.E)
        zipcode_entry.grid(column=1, row=0, sticky=tkinter.W)
        zipcode_note_label.grid(column=0, row=1, columnspan=2, sticky=tkinter.N)
        latlon_frame.columnconfigure(0, weight=1)
        latlon_frame.columnconfigure(1, weight=1)
        latlon_frame.columnconfigure(2, weight=1)
        latlon_frame.columnconfigure(3, weight=1)
        latlon_frame.rowconfigure(0, weight=1)
        latlon_frame.rowconfigure(1, weight=1)
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
        boktai1_logo.grid(column=0, row=2, columnspan=8)
        if self.config.version != 1:
            boktai1_logo.grid_remove()
        boktai_2_logo.grid(column=0, row=2, columnspan=8)
        if self.config.version != 2:
            boktai_2_logo.grid_remove()
        boktai_3_logo.grid(column=0, row=2, columnspan=8)
        if self.config.version != 3:
            boktai_3_logo.grid_remove()
        boktai_meter_frame.grid(column=0, row=3, columnspan=8)
        boktai1_meter_bg.grid(column=0, row=4, columnspan=8)
        boktai1_meter_fg.grid(column=0, row=4, columnspan=8)
        if self.config.version != 1:
            boktai1_meter_bg.grid_remove()
            boktai1_meter_fg.grid_remove()
        boktai2_meter_bg.grid(column=0, row=4, columnspan=8)
        boktai2_meter_fg.grid(column=0, row=4, columnspan=8)
        if self.config.version != 2:
            boktai2_meter_bg.grid_remove()
            boktai2_meter_fg.grid_remove()
        boktai3_meter_bg.grid(column=0, row=4, columnspan=8)
        boktai3_meter_fg.grid(column=0, row=4, columnspan=8)
        if self.config.version != 3:
            boktai3_meter_bg.grid_remove()
            boktai3_meter_fg.grid_remove()
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
        api_update_mute_separator.grid(column=0, row=3, columnspan=2, sticky=tkinter.EW, pady=(5, 5))
        mute_frame.grid(column=0, row=4, columnspan=2, padx=(10, 10))
        mute_flavor_checkbutton.grid(column=0, row=0, columnspan=2, padx=(5, 5))
        mute_alert_checkbutton.grid(column=2, row=0, columnspan=2, padx=(5, 5))
        alert_sound_label.grid(column=2, row=1)
        alert_sound_option.grid(column=3, row=1)
        mute_lunar_mode_separator.grid(column=0, row=5, columnspan=2, sticky=tkinter.EW, pady=(5, 5))
        lunar_mode_checkbutton.grid(column=0, row=6, columnspan=2)
        lunar_mode_notes_label.grid(column=0, row=7, columnspan=2)
        lunar_mode_theme_separator.grid(column=0, row=8, columnspan=2, sticky=tkinter.EW, pady=(5, 5))
        theme_picker_frame.grid(column=0, row=9, columnspan=2, padx=(10, 10))
        theme_label.grid(column=0, row=0)
        theme_option.grid(column=1, row=0)
        temp_scale_frame.grid(column=2, row=0, columnspan=2, padx=(10, 10))
        fahrenheit_radio.grid(column=0, row=0, sticky=tkinter.W)
        celsuis_radio.grid(column=1, row=0, sticky=tkinter.E)

        logging_frame.columnconfigure(0, weight=1)
        logging_frame.rowconfigure(0, weight=1)
        logging_text.grid(column=0, row=0, sticky=tkinter.NSEW)

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

    def on_close(self, event=None) -> None:
        self.logger.info('Quitting')
        self.play_sound('close')
        self.window.destroy()

    def do_update(self) -> None:
        logging.debug('Performing update')
        if self._first_update:
            self._first_update = False
            self.timed_update()
            return
        self.config.version = int(self._widget_dict['version_combo'].get())
        if not 0 < self.config.version < 4:
            self.play_sound('warning')
            messagebox.showwarning('Warning', 'Boktai version must be between 1 and 3.')
            return
        update_logo = False
        if (self.boktaisim and self._last_version != self.version) or \
                (not self.boktaisim):
            update_logo = True
            self._last_version = self.version
        notebook = self._widget_dict['area_notebook']
        current_location_tab = notebook.tab(notebook.select(), "text")
        latlong = None
        if current_location_tab == 'Zipcode':
            try:
                self.config.zipcode = int(
                    self._widget_dict['zipcode_entry'].get()
                )
            except ValueError:
                self.alert('warning', 'No zipcode provided.')
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
            self.config.lat = self._widget_dict['lat_entry'].get()
            self.config.lon = self._widget_dict['lon_entry'].get()
            latlong = f'{self.config.lat},{self.config.lon}'
        elif current_location_tab == 'Manual':
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
                state='Nowhere',
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
        bar_value = self.boktaisim.value
        self._widget_dict[f'boktai{self.config.version}_meter_fg'].configure(
            width=BOKTAI_METER[self.config.version][bar_value]
        )
        if self._last_value != bar_value:
            self.play_sound('bar_update')
        self._last_value = bar_value
        self.config.save()

    def alert(self, level: str, msg: str):
        self.play_sound(level)
        messagebox.showwarning(level, msg)
        logging.log(logging._nameToLevel[level.upper()], msg)

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
            name='boktai1_logo'
        )
        version_label = tkinter.Label(
            about_window, text=f'Version {__version__}', fg="gray33", font=("TkDefaultFont", 10),
            bg='#ECECEC', highlightbackground='#ECECEC'
        )
        more_info_frame = tkinter.Frame(about_window, border=3, relief='ridge')
        credits_idea_pre = tkinter.Label(more_info_frame, text='Idea by Nathan Stiles of')
        credits_idea_post = tkinter.Label(
            more_info_frame, text=f'Stiles\' Reviews', fg="blue", cursor="hand"
        )
        credits_coding_pre = tkinter.Label(more_info_frame, text='Original code by')
        credits_coding_post = tkinter.Label(
            more_info_frame, text='Connor Barthold', fg='blue', cursor='hand'
        )
        credits_api_pre = tkinter.Label(more_info_frame, text='Uses the free')
        credits_api_post = tkinter.Label(
            more_info_frame, text='MetaWeather API', fg='blue', cursor='hand'
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
        def _launch_browser(event: Optional = None):
            webbrowser.open(url=url)
        return _launch_browser

    def _wrap_option(self, widget_label: str, option_label: Optional[str] = None):
        def _option_setter(event: Optional = None):
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

    def _update_temp_scale(self, event=None):
        if self.config.temp_scale != self._tk_variables['temp_scale'].get():
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
                min_f = round(c_to_f(self._widget_dict['min_f_entry'].get()), 2)
                self._widget_dict['min_f_entry'].delete(0, tkinter.END)
                self._widget_dict['min_f_entry'].insert(
                    0, min_f
                )
                avg_f = round(c_to_f(self._widget_dict['avg_f_entry'].get()), 2)
                self._widget_dict['avg_f_entry'].delete(0, tkinter.END)
                self._widget_dict['avg_f_entry'].insert(
                    0, avg_f
                )
                max_f = round(c_to_f(self._widget_dict['max_f_entry'].get()), 2)
                self._widget_dict['max_f_entry'].delete(0, tkinter.END)
                self._widget_dict['max_f_entry'].insert(
                    0, max_f
                )
            if self.config.temp_scale == 'C':
                min_f = round(f_to_c(self._widget_dict['min_f_entry'].get()), 2)
                self._widget_dict['min_f_entry'].delete(0, tkinter.END)
                self._widget_dict['min_f_entry'].insert(
                    0, min_f
                )
                avg_f = round(f_to_c(self._widget_dict['avg_f_entry'].get()), 2)
                self._widget_dict['avg_f_entry'].delete(0, tkinter.END)
                self._widget_dict['avg_f_entry'].insert(
                    0, avg_f
                )
                max_f = round(f_to_c(self._widget_dict['max_f_entry'].get()), 2)
                self._widget_dict['max_f_entry'].delete(0, tkinter.END)
                self._widget_dict['max_f_entry'].insert(
                    0, max_f
                )

    def _update_theme(self, event=None):
        tkinter.ttk.Style().theme_use(self._tk_variables['theme'].get())
        self.config.theme = self._tk_variables['theme'].get()
        self.logger.info(f'Updating theme to `{self.config.theme}`')
        self.config.save()

    def _set_alert_sound(self, event=None):
        selection = self._tk_variables["alert_sound_option"].get()
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
    def version(self):
        return self.config.version

    @version.setter
    def version(self, value):
        assert isinstance(value, int)
        self.config.version = value

    @property
    def lunar_mode(self):
        return self.config.lunar_mode

    @lunar_mode.setter
    def lunar_mode(self, value):
        assert isinstance(value, bool)
        self.config.lunar_mode = value


class TextHandler(logging.Handler):
    """This class allows you to log to a Tkinter Text or ScrolledText widget"""

    def __init__(self, text):
        # run the regular Handler __init__
        logging.Handler.__init__(self)
        # Store a reference to the Text it will log to
        self.text = text

    def emit(self, record):
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
