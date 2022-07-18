#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime

LOCAL_TIMEZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

# Openmeteo uses different weather codes than metaweather, and they don't always neatly mesh.
OPENMETEO_WEATHER_STATES = {
    0: 'c',     # Clear Sky
    1: 'lc',    # Mainly Clear
    2: 'lc',    # Partly Cloudy
    3: 'hc',    # Overcast
    45: 'hc',   # Fog
    48: 'hc',   # Depositing Rime Fog (Freezing Ice Fog)
    51: 's',    # Light Drizzle
    53: 's',    # Moderate Drizzle
    55: 'lr',   # Dense Drizzle
    56: 's',    # Light Freezing Drizzle
    57: 'lr',   # Dense Freezing Drizzle
    61: 'lr',   # Slight Rain
    63: 'hr',   # Moderate Rain
    65: 'hr',   # Heavy Rain
    66: 'lr',   # Light Freezing Rain
    67: 'h',    # Heavy Freezing Rain
    71: 'sn',   # Slight Snow Fall
    73: 'sn',   # Moderate Snow Fall
    75: 'sn',   # heavy Snow Fall
    77: 'sn',   # Snow Grains
    80: 'hr',   # Slight Rain Showers
    81: 'hr',   # Moderate Rain Showers
    82: 'hr',   # Violent Rain Showers
    85: 'sl',   # Slight Snow Showers
    86: 'h',    # Heavy Snow Showers
    95: 't',    # Slight or Moderate Thunderstorm
    96: 't',    # Thunderstorm with Slight Hail
    99: 't'     # Thunderstorm with Heavy Hail
}

WEATHER_STATES = {
    'sn': {
        'name': 'Snow',
        'min': 0,
        'avg': 2,
        'max': 5,
        'mod': 0
    },
    'sl': {
        'name': 'Sleet',
        'min': 0,
        'avg': 1,
        'max': 3,
        'mod': -2
    },
    'h': {
        'name': 'Hail',
        'min': 0,
        'avg': 1,
        'max': 3,
        'mod': -2
    },
    't': {
        'name': 'Thunderstorm',
        'min': 0,
        'avg': 1,
        'max': 2,
        'mod': -2
    },
    'hr': {
        'name': 'Heavy Rain',
        'min': 0,
        'avg': 2,
        'max': 4,
        'mod': -1
    },
    'lr': {
        'name': 'Light Rain',
        'min': 0,
        'avg': 3,
        'max': 8,
        'mod': 0
    },
    's': {
        'name': 'Showers',
        'min': 1,
        'avg': 5,
        'max': 9,
        'mod': 1
    },
    'hc': {
        'name': 'Heavy Cloud',
        'min': 0,
        'avg': 2,
        'max': 4,
        'mod': -1
    },
    'lc': {
        'name': 'Light Cloud',
        'min': 2,
        'avg': 5,
        'max': 10,
        'mod': 1
    },
    'c': {
        'name': 'Clear',
        'min': 4,
        'avg': 7,
        'max': 10,
        'mod': 1
    },
}

WEATHER_STATES_REVERSE = {
    'Snow': 'sn',
    'Sleet': 'sl',
    'Hail': 'h',
    'Thunderstorm': 't',
    'Heavy Rain': 'hr',
    'Light Rain': 'lr',
    'Showers': 's',
    'Heavy Cloud': 'hc',
    'Light Cloud': 'lc',
    'Clear': 'c'
}

SUN_STATES = {
    'sunrise': {
        'name': 'Sunrise',
        'icon': 'Rising.gif'
    },
    'rise': {
        'name': 'Rising',
        'icon': 'Rising.gif'
    },
    'apex': {
        'name': 'At Apex',
        'icon': 'At Apex.gif'
    },
    'descend': {
        'name': 'Descending',
        'icon': 'Descending.gif'
    },
    'sunset': {
        'name': 'Sunset',
        'icon': 'Descending.gif'
    },
    'moon': {
        'name': 'Moonlight',
        'icon': 'Moonlight.gif'
    },
}

FEATURE_WEIGHTS = {
    'temperature': 10,
    'weather': 20,
    'sun_location': 40,
    'random': 25
}

# Pixel offsets for the stages of the various meters
BOKTAI_METER = {
    1: {
        0: 0,
        1: 77,
        2: 104,
        3: 131,
        4: 158,
        5: 185,
        6: 212,
        7: 239,
        8: 266
    },
    2: {
        0: 0,
        1: 30,
        2: 57,
        3: 84,
        4: 111,
        5: 138,
        6: 165,
        7: 192,
        8: 219,
        9: 246,
        10: 275
    },
    3: {
        0: 0,
        1: 30,
        2: 57,
        3: 84,
        4: 111,
        5: 138,
        6: 165,
        7: 192,
        8: 219,
        9: 246,
        10: 275
    }
}

# List of all images to load at start
IMAGES = [
    'boktai1_logo.gif',
    'boktai2_logo.gif',
    'boktai3_logo.gif',
    'boktai1_meter_empty.jpg',
    'boktai1_meter_full.jpg',
    'boktai2_meter_empty.jpg',
    'boktai2_meter_full.jpg',
    'boktai3_meter_empty.jpg',
    'boktai3_meter_full.jpg',
    'Solar_Sensor_Icon.gif',
    'boktaisim_icon.gif',
    'boktaisim_icon.ico',
    'boktaisim_icon.icns',
    'Rising.gif',
    'At Apex.gif',
    'Descending.gif',
    'Moonlight.gif',
    'sn.gif',
    'sl.gif',
    'h.gif',
    't.gif',
    'hr.gif',
    'lr.gif',
    's.gif',
    'hc.gif',
    'lc.gif',
    'c.gif'
]

SOUNDS = {
    'open': {
        'file': 'open.wav',
        'type': 'flavor'
    },
    'bar_update': {
        'file': 'chime1.wav',
        'type': 'alert'
    },
    'warning': {
        'file': 'overheat.wav',
        'type': 'alert'
    },
    'about': {
        'file': 'otenko.wav',
        'type': 'flavor'
    },
    'close': {
        'file': 'close.wav',
        'type': 'flavor'
    }
}
