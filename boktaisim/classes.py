#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import appdirs
import datetime
import json
import logging
import pathlib
import random
import requests
from typing import Optional, TYPE_CHECKING, Union

from .constants import FEATURE_WEIGHTS, WEATHER_STATES
from .utils import get_state

import pyzipcode

BOKTAI_STATE = get_state()
if BOKTAI_STATE == ('mac', 'frozen', 'app'):
    pyzipcode.db_location = 'zipcodes.db'
elif BOKTAI_STATE[0:2] == ('windows', 'frozen'):
    pyzipcode.db_location = 'resources/zipcodes.db'
else:
    pass

if TYPE_CHECKING:
    from .gui import WindowManager


class BoktaiConfig(object):
    """
    Configuration abstraction for boktaisim.

    Arguments:

    gui_update_interval:    How often the gui should update, in seconds
    api_update_interval:    How often to pull new data from the metaweather API, in seconds
    version:                The last boktai version set in the gui
    mute_alert_sounds:      Mute update and error sounds
    mute_flavor_sounds:     Mute flavor sounds (startup, about, close, etc.)
    area_type:              Which area type was last selected in the gui, can be 'zipcode',
                            'latlon', or 'manual'
    zipcode:                Last zipcode set in the gui
    lat:                    Last latitude set in the gui
    lon:                    Last longitude set in the gui
    min_f:                  Last minimum temperature set in the gui, in degrees fahrenheit
    avg_f:                  Last average temperature set in the gui, in degrees fahrenheit
    max_f:                  Last maximum temperature set in the gui, in degrees fahrenheit
    weather:                Last weather state set in the gui, can be and valid shorthand from
                            `WEATHER_STATES` variable
    sunrise:                Last sunrise time set in the gui, in either '%H:%M' or '%I:%m:%p' format
    sunset:                 Last sunset time set in the gui, in either '%H:%M' or '%I:%m:%p' format
    lunar_mode:             Enable lunar mode
    theme:                  Which tkinter theme to use
    temp_scale:             F for Fahrenheit of C for Celsius
    alert_sound_option:     Which wav file to use for alert sounds
    config_file:            Path to the config file
    """

    def __init__(
            self,
            gui_update_interval: int = 300,
            api_update_interval: int = 900,
            version: int = 1,
            mute_alert_sounds: bool = False,
            mute_flavor_sounds: bool = False,
            area_type: Optional[str] = None,
            zipcode: Optional[int] = None,
            lat: Optional[float] = None,
            lon: Optional[float] = None,
            min_f: Optional[float] = None,
            avg_f: Optional[float] = None,
            max_f: Optional[float] = None,
            weather: Optional[str] = None,
            sunrise: Optional[str] = None,
            sunset: Optional[str] = None,
            lunar_mode: Optional[bool] = False,
            theme: Optional[str] = 'default',
            temp_scale: Optional[str] = 'F',
            alert_sound_option: Optional[str] = 'chime1',
            logging_level: Optional[str] = 'INFO',
            config_file: Optional[str] = None
    ) -> None:
        self.gui_update_interval = gui_update_interval
        self.api_update_interval = api_update_interval
        self.version = version
        self.mute_alert_sounds = mute_alert_sounds
        self.mute_flavor_sounds = mute_flavor_sounds
        self.area_type = area_type
        self.zipcode = zipcode
        self.lat = lat
        self.lon = lon
        self.min_f = min_f
        self.avg_f = avg_f
        self.max_f = max_f
        self.weather = weather
        self.sunrise = sunrise
        self.sunset = sunset
        self.lunar_mode = lunar_mode
        self.theme = theme
        self.temp_scale = temp_scale
        self.alert_sound_option = alert_sound_option
        self.logging_level = logging_level
        if config_file is None:
            config_file = str(
                pathlib.Path(
                    appdirs.user_config_dir(__name__, 'c0nch0b4r')
                ) / 'config.json'
            )
        self.config_file = config_file
        self.save()

    @classmethod
    def from_json(cls, config_file: Optional[str] = None) -> BoktaiConfig:
        config = {}
        if not config_file:
            config_file = str(
                pathlib.Path(
                    appdirs.user_config_dir(__name__, 'c0nch0b4r')
                ) / 'config.json'
            )
        config_file = str(pathlib.Path(config_file).expanduser().resolve())
        try:
            with open(config_file, 'r') as fp:
                config = json.load(fp=fp)
        except OSError:
            logging.info('Could not open config file path, using defaults')
        config['config_file'] = config_file
        return cls(**config)

    def save(self) -> None:
        config_path = pathlib.Path(self.config_file)
        if not config_path.exists():
            try:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.touch()
            except OSError:
                logging.warning(f'Could not create config file at `{config_path}`, not saving')
                return
        config_json = {}
        for key, value in self.__dict__.items():
            if key.startswith('_') or key == 'config_file':
                continue
            config_json[key] = value
        try:
            with config_path.open('w') as cfp:
                json.dump(config_json, cfp, indent=4)
        except OSError:
            logging.warning(f'Could not write json to config file at `{config_path}`, not saving')


class WeatherInfo(object):
    def __init__(
            self,
            state: str,
            city: str,
            latlong: str,
            woeid: str,
            min_temp: float,
            max_temp: float,
            current_temp: float,
            visibility: int,
            weather_state: str,
            sunrise: str,
            sunset: str,
            timestamp: str,
            avg_temp: Optional[float] = None,
            raw_weather_data: Optional[dict] = None,
            woeid_options: Optional[dict] = None,
            manual: bool = False
    ) -> None:
        self.state = state
        self.city = city
        self.latlong = latlong
        self.woeid = woeid
        self.min_temp = min_temp
        self.max_temp = max_temp
        self._current_temp = current_temp
        if self._current_temp >= self.max_temp:
            self.max_temp = self._current_temp
        if self._current_temp <= self.min_temp:
            self.min_temp = self._current_temp
        self.visibility = visibility
        self.weather_state = weather_state
        self.sunrise = sunrise
        self.sunset = sunset
        self.timestamp = timestamp
        self.avg_temp = avg_temp
        self.manual = manual
        self._last_update = datetime.datetime.now()
        self._raw_data = raw_weather_data
        self._woeid_options = woeid_options

    def update(self) -> None:
        if self.manual:
            self._last_update = datetime.datetime.now()
            return
        weather_req = requests.get(f'https://www.metaweather.com/api/location/{self.woeid}/')
        weather_json = weather_req.json()
        self._raw_data = weather_json
        latest_weather = weather_json['consolidated_weather'][-1]
        self.timestamp = latest_weather['created']
        self.sunrise = weather_json['sun_rise']
        self.sunset = weather_json['sun_set']
        self.weather_state = latest_weather['weather_state_abbr']
        self.min_temp = latest_weather['min_temp']
        self.max_temp = latest_weather['max_temp']
        self._current_temp = latest_weather['the_temp']
        if self._current_temp > self.max_temp:
            self.max_temp = self._current_temp
        if self._current_temp < self.min_temp:
            self.min_temp = self._current_temp
        self.visibility = latest_weather['visibility']
        self._last_update = datetime.datetime.now()

    @property
    def weather_timestamp(self) -> datetime.datetime:
        return datetime.datetime.strptime(self.timestamp, '%Y-%m-%dT%H:%M:%S.%f%z')

    @property
    def sunrise_timestamp(self) -> datetime.datetime:
        if len(self.sunset) == 32:
            tz = self.sunrise[-6:-3]
            tz += self.sunrise[-2:]
            return datetime.datetime.strptime(self.sunrise[:-6] + tz, '%Y-%m-%dT%H:%M:%S.%f%z')
        else:
            return datetime.datetime.strptime(self.sunrise, '%Y-%m-%dT%H:%M:%S.%f%z')

    @property
    def sunset_timestamp(self) -> datetime.datetime:
        if len(self.sunset) == 32:
            tx = self.sunset[-6:-3]
            tx += self.sunset[-2:]
            return datetime.datetime.strptime(self.sunset[:-6] + tx, '%Y-%m-%dT%H:%M:%S.%f%z')
        else:
            return datetime.datetime.strptime(self.sunset, '%Y-%m-%dT%H:%M:%S.%f%z')

    @property
    def sun_position(self) -> float:
        seconds_of_daylight = round(
            (self.sunset_timestamp - self.sunrise_timestamp).total_seconds()
        )
        seconds_left = round(
            (self.sunset_timestamp - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        )
        seconds_offest = seconds_of_daylight - seconds_left
        try:
            return clamp_and_scale(
                0,
                seconds_of_daylight,
                0,
                100,
                seconds_offest
            )
        except AssertionError:
            return -1

    @property
    def sun_state(self) -> str:
        if 0 <= self.sun_position <= 30:
            return 'Rising'
        if 0 <= self.sun_position <= 70:
            return 'At Apex'
        if 0 <= self.sun_position <= 99.9:
            return 'Descending'
        return 'Moonlight'

    def data_age(self) -> int:
        return round((datetime.datetime.now() - self._last_update).total_seconds())

    @classmethod
    def from_latlong(cls, latitude: float, longitude: float) -> WeatherInfo:
        latlong = str(latitude) + ',' + str(longitude)
        location_req = requests.get(
            f'https://www.metaweather.com/api/location/search/?lattlong={latlong}'
        )
        location_json = location_req.json()
        closest_woeid = location_json[0]['woeid']
        weather_req = requests.get(f'https://www.metaweather.com/api/location/{closest_woeid}/')
        weather_json = weather_req.json()
        latest_weather = weather_json['consolidated_weather'][-1]
        return cls(
            state=weather_json['parent']['title'],
            city=weather_json['title'],
            latlong=latlong,
            woeid=closest_woeid,
            min_temp=latest_weather['min_temp'],
            max_temp=latest_weather['max_temp'],
            current_temp=latest_weather['the_temp'],
            visibility=latest_weather['visibility'],
            weather_state=latest_weather['weather_state_abbr'],
            sunrise=weather_json['sun_rise'],
            sunset=weather_json['sun_set'],
            timestamp=latest_weather['created'],
            raw_weather_data=weather_json,
            woeid_options=location_json
        )

    @classmethod
    def from_zip(cls, zipcode: int) -> WeatherInfo:
        latlong = zip_to_latlong(zipcode)
        location_req = requests.get(
            f'https://www.metaweather.com/api/location/search/?lattlong={latlong}'
        )
        location_json = location_req.json()
        closest_woeid = location_json[0]['woeid']
        weather_req = requests.get(f'https://www.metaweather.com/api/location/{closest_woeid}/')
        weather_json = weather_req.json()
        latest_weather = weather_json['consolidated_weather'][-1]
        return cls(
            state=weather_json['parent']['title'],
            city=weather_json['title'],
            latlong=latlong,
            woeid=closest_woeid,
            min_temp=latest_weather['min_temp'],
            max_temp=latest_weather['max_temp'],
            current_temp=latest_weather['the_temp'],
            visibility=latest_weather['visibility'],
            weather_state=latest_weather['weather_state_abbr'],
            sunrise=weather_json['sun_rise'],
            sunset=weather_json['sun_set'],
            timestamp=latest_weather['created'],
            raw_weather_data=weather_json,
            woeid_options=location_json
        )

    @property
    def current_temp(self) -> float:
        if self.manual:
            return round(random.triangular(self.min_temp, self.max_temp, mode=self.avg_temp), 2)
        return self._current_temp

    @property
    def min_temp_f(self) -> int:
        return round(c_to_f(self.min_temp), 2)

    @property
    def max_temp_f(self) -> int:
        return round(c_to_f(self.max_temp), 2)

    @property
    def current_temp_f(self) -> int:
        return round(c_to_f(self.current_temp), 2)


class BoktaiSim(object):
    def __init__(
            self,
            version: Optional[int] = None,
            latlon: Optional[str] = None,
            zipcode: Optional[int] = None,
            lunar_mode: Optional[bool] = None,
            manual_data: Optional[WeatherInfo] = None,
            parent: Optional[WindowManager] = None
    ) -> None:
        if not version and not parent:
            raise ValueError('No version provided')
        if version and 0 < version < 4:
            self._version = version
        elif version:
            raise ValueError('version must be between 1 and 3')
        self.latlon = latlon
        if self.latlon:
            lat = float(latlon.split(',')[0])
            lon = float(latlon.split(',')[1])
            self.weather = WeatherInfo.from_latlong(latitude=lat, longitude=lon)
        self.zipcode = zipcode
        if self.zipcode:
            self.weather = WeatherInfo.from_zip(self.zipcode)
        self._lunar_mode = lunar_mode
        if not self._lunar_mode and not parent:
            self._lunar_mode = False
        if manual_data:
            self.weather = manual_data
        self.parent = parent

    def __str__(self) -> str:
        location_length = len(self.weather.city) + len(self.weather.state)
        temp_length = len(str(self.weather.min_temp_f)) + len(str(self.weather.max_temp_f)) + \
            len(str(self.weather.current_temp_f))
        return_str = '╭── Stiles\' Solar Simulator for the Boktai Trilogy ──╮\n'
        return_str += '│' + (' ' * 52) + '│\n'
        return_str += f'│   Location: {self.weather.city}, {self.weather.state}' + \
                      (' ' * (52 - location_length - 15)) + '│\n'
        return_str += f'│   Min: {self.weather.min_temp_f}°F, Current: ' \
                      f'{self.weather.current_temp_f}°F, Max: {self.weather.max_temp_f}°F' + \
                      (' ' * (52 - temp_length - 32)) + '│\n'
        return_str += f'│   Boktai {self.version} Gauge' + (' ' * 35) + '│\n'
        if self.version == 1:
            return_str += '│' + (' ' * 18) + '╔' + ('═╤' * 7) + '═╗' + (' ' * 17) + '│\n'
            if self.temperature_value == 8:
                return_str += '│' + (' ' * 18) + '║▓│▓│▓│▓│▓│▓│▓│▓║' + (' ' * 17) + '│\n'
            elif 1 <= self.temperature_value <= 6:
                return_str += '│' + (' ' * 18) + '║' + ('▓│' * self.temperature_value) + (
                        ' │' * (8 - self.temperature_value - 1)) + ' ║' + (' ' * 17) + '│\n'
            else:
                return_str += '│' + (' ' * 18) + '║' + ('▓│' * self.temperature_value) + (
                        ' │' * (8 - self.temperature_value)) + '║' + (' ' * 17) + '│\n'
            return_str += '│' + (' ' * 18) + '╚' + ('═╧' * 7) + '═╝' + (' ' * 17) + '│\n'
        elif self.version == 2 or self.version == 3:
            return_str += '│' + (' ' * 16) + '╔' + ('═╤' * 9) + '═╗' + (' ' * 15) + '│\n'
            if self.temperature_value == 10:
                return_str += '│' + (' ' * 16) + '║▓│▓│▓│▓│▓│▓│▓│▓│▓│▓║' + (' ' * 15) + '│\n'
            elif 1 <= self.temperature_value <= 9:
                return_str += '│' + (' ' * 16) + '║' + ('▓│' * self.temperature_value) + (
                        ' │' * (10 - self.temperature_value - 1)) + ' ║' + (' ' * 15) + '│\n'
            else:
                return_str += '│' + (' ' * 16) + '║' + ('▓│' * self.temperature_value) + (
                        ' │' * (10 - self.temperature_value)) + '║' + (' ' * 15) + '│\n'
            return_str += '│' + (' ' * 16) + '╚' + ('═╧' * 9) + '═╝' + (' ' * 15) + '│\n'
        return_str += '│' + (' ' * 52) + '│\n'
        return_str += '╰' + ('─' * 52) + '╯'
        return return_str

    @property
    def version(self) -> int:
        if self.parent:
            return self.parent.version
        return self._version

    @version.setter
    def version(self, value: int) -> None:
        assert isinstance(value, int)
        assert 0 < value < 4
        if self.parent:
            self.parent.version = value
        else:
            self._version = value

    @property
    def lunar_mode(self) -> bool:
        if self.parent:
            return self.parent.lunar_mode
        return self._lunar_mode

    @lunar_mode.setter
    def lunar_mode(self, value: bool):
        if self.parent:
            self.parent.lunar_mode = value
        else:
            self._lunar_mode = value

    @property
    def weather_min(self) -> int:
        return WEATHER_STATES[self.weather.weather_state]['min']

    @property
    def weather_avg(self) -> int:
        return WEATHER_STATES[self.weather.weather_state]['avg']

    @property
    def weather_max(self) -> int:
        return WEATHER_STATES[self.weather.weather_state]['max']

    @property
    def sun_value(self) -> float:
        return self._calulate_sun_value(self.weather.sun_position)

    @staticmethod
    def _calulate_sun_value(
            sun_position: float,
            alpha_min: int = 225,
            alpha_max: int = 550,
            beta_min: int = 225,
            beta_max: int = 225
    ) -> float:
        if sun_position == 100.0 or sun_position == -1:
            return 0
        if sun_position > 50:
            sun_position = 100 - sun_position
        if alpha_min < alpha_max:
            alpha_precursor = clamp_and_scale(
                old_min_value=0,
                old_max_value=100,
                new_min_value=alpha_min,
                new_max_value=alpha_max,
                current_value=sun_position
            )
            alpha = alpha_precursor / 100
        else:
            alpha = alpha_max / 100
        if beta_min < beta_max:
            beta_precursor = clamp_and_scale(
                old_min_value=0,
                old_max_value=100,
                new_min_value=beta_min,
                new_max_value=beta_max,
                current_value=sun_position
            )
            beta = beta_precursor / 100
        else:
            beta = beta_max / 100
        random_value = random.betavariate(alpha, beta) * 10
        if sun_position <= 5 and random_value > 2:
            random_value -= 2
        return random_value

    @property
    def temperature_value(self) -> float:
        return clamp_and_scale(
            self.weather.min_temp,
            self.weather.max_temp,
            0,
            10,
            self.weather.current_temp
        )

    @property
    def random_weather_value(self) -> float:
        return random.triangular(
            self.weather_min,
            self.weather_max,
            self.weather_avg
        )

    @property
    def weather_value(self) -> float:
        return clamp_and_scale(
            self.weather.min_temp,
            self.weather.max_temp,
            self.weather_min,
            self.weather_max,
            self.weather.current_temp
        )

    @property
    def random_sun_value(self) -> float:
        return self._calulate_sun_value(self.weather.sun_position)

    @property
    def value(self) -> int:
        """ Return weighted average of all values, only polling random ones once. """
        values = {
            'temperature': self.temperature_value,
            'weather': self.weather_value,
            'sun_location': self.random_sun_value,
            'random': self.random_weather_value
        }
        logging.debug(f'Generated values: {values}')
        value_sum = 0
        value_count = 0
        value_names = ['temperature', 'weather', 'sun_location', 'random']
        for value_name in value_names:
            value_sum += values[value_name] * FEATURE_WEIGHTS[value_name]
            value_count += FEATURE_WEIGHTS[value_name]
        logging.debug(f'Number of values: {value_count}, Sum Total: {value_sum}')
        logging.debug(f'Sun position: {self.weather.sun_position}')
        if self.lunar_mode and \
                (self.weather.sun_position == 100.0 or self.weather.sun_position == -1):
            return round(self._version_return(value_sum / value_count / 2))
        if self.weather.sun_position == 100.0 or self.weather.sun_position == -1:
            return 0
        initial_result = value_sum / value_count
        initial_result = initial_result + WEATHER_STATES[self.weather.weather_state]['mod']
        if initial_result > 10:
            initial_result = 10
        if initial_result < 0:
            initial_result = 0
        final_result = round(self._version_return(initial_result))
        logging.debug(f'Final Bar Value: {final_result}')
        return final_result

    def _version_return(
            self,
            value: float
    ) -> float:
        if self.version == 1:
            return self._return_v1(value=value)
        return value

    @staticmethod
    def _return_v1(value: float) -> float:
        return clamp_and_scale(
            old_min_value=0,
            old_max_value=10,
            new_min_value=0,
            new_max_value=8,
            current_value=value
        )


class Temperature(object):
    def __init__(
            self,
            value: Union[str, float, str],
            scale: Optional[str] = 'F'
    ) -> None:
        self.value = float(value)
        scale = scale.upper()
        if scale not in ('F', 'C'):
            raise ValueError('mode must be one of (F, C)')
        self.scale = scale

    @property
    def celsius(self) -> float:
        if self.scale == 'F':
            return self.f_to_c(self.value)
        return self.value

    @property
    def fahrenheit(self) -> float:
        if self.scale == 'C':
            return self.c_to_f(self.value)
        return self.value

    @staticmethod
    def f_to_c(fahrenheit: float) -> float:
        celsius = (fahrenheit - 32) * 5 / 9
        return celsius

    @staticmethod
    def c_to_f(celsius: float) -> float:
        fahrenheit = (celsius * 9 / 5) + 32
        return fahrenheit


def f_to_c(fahrenheit: Union[str, float, int]) -> float:
    celsius = (float(fahrenheit) - 32) * 5 / 9
    return celsius


def c_to_f(celsius: Union[str, float, int]) -> float:
    fahrenheit = (float(celsius) * 9 / 5) + 32
    return fahrenheit


def check_api() -> bool:
    try:
        requests.get('https://www.metaweather.com/api/')
        return True
    except requests.exceptions.ConnectionError:
        return False


def clamp_and_scale(
        old_min_value: float,
        old_max_value: float,
        new_min_value: float,
        new_max_value: float,
        current_value: float
) -> float:
    if current_value > old_max_value:
        old_max_value = current_value
    assert old_min_value <= current_value <= old_max_value
    assert new_min_value < new_max_value
    old_range = old_max_value - old_min_value
    new_range = new_max_value - new_min_value
    scaled_value = (((current_value - old_min_value) * new_range) / old_range) + new_min_value
    return scaled_value


def zip_to_latlong(zip_code: int) -> Optional[str]:
    zip_db = pyzipcode.ZipCodeDatabase()
    return ','.join([str(zip_db[zip_code].latitude), str(zip_db[zip_code].longitude)])


def check_latlong(lat: float, lon: float) -> bool:
    if not -90 <= lat <= 90:
        return False
    if not -180 <= lon <= 180:
        return False
    return True
