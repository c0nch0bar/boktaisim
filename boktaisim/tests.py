#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest

from .classes import BoktaiSim, WeatherInfo
from .constants import WEATHER_STATES

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.ticker import AutoMinorLocator


def comprehensive_test():
    fig, axs = plt.subplots(3, 3, figsize=(10, 10))
    plt.subplots_adjust(left=0.05, bottom=0.15, right=0.95, top=0.95, wspace=0.2, hspace=0.3)

    ax_sun = plt.axes([0.2, 0.06, 0.65, 0.01], facecolor='lightgoldenrodyellow')
    slider_sun = Slider(ax_sun, 'Sun Position', 0., 100.,
                        valinit=50, valstep=1)

    ax_max_temp = plt.axes([0.2, 0.047, 0.65, 0.01], facecolor='lightgoldenrodyellow')
    slider_max_temp = Slider(ax_max_temp, 'Max Temperature', 0., 100.,
                             valinit=90., valstep=None)

    ax_avg_temp = plt.axes([0.2, 0.034, 0.65, 0.01], facecolor='lightgoldenrodyellow')
    slider_avg_temp = Slider(ax_avg_temp, 'Avg Temperature', 0., 100.,
                             valinit=50., valstep=None)

    ax_min_temp = plt.axes([0.2, 0.021, 0.65, 0.01], facecolor='lightgoldenrodyellow')
    slider_min_temp = Slider(ax_min_temp, 'Min Temperature', 0., 100.,
                             valinit=0., valstep=None)

    ax_temp = plt.axes([0.2, 0.008, 0.65, 0.01], facecolor='lightgoldenrodyellow')
    slider_temp = Slider(ax_temp, 'Current Temperature', 0., 100.,
                         valinit=50., valstep=None)

    colors = {
        'temperature': 'red',
        'weather': 'blue',
        'sun_location': 'orange',
        'random': 'green',
        'total': 'gray'
    }
    labels = list(colors.keys())

    global min_temp, avg_temp, max_temp, current_temp, sun_value
    min_temp = 0.
    avg_temp = 50.
    max_temp = 100.
    current_temp = 50.
    sun_value = 50

    print('PING')

    def _wrap_update(variable: str):
        def update(value=None):
            global min_temp, avg_temp, max_temp, current_temp, sun_value
            if variable == 'current_temp':
                current_temp = value
            if variable == 'min_temp':
                min_temp = value
            if variable == 'avg_temp':
                avg_temp = value
            if variable == 'max_temp':
                max_temp = value
            if variable == 'sun_value':
                sun_value = value
            i = 0
            j = 0
            for state in WEATHER_STATES:
                if state == 'sl':
                    continue
                results = general_test(
                    weather_state=state, min_temp=min_temp, max_temp=max_temp, avg_temp=avg_temp,
                    current_temp=current_temp, sun_value=sun_value, count=1000, version=1
                )
                axs[j, i].clear()
                axs[j, i].set_xticks(results[1])
                axs[j, i].xaxis.set_minor_locator(AutoMinorLocator(n=2))
                axs[j, i].tick_params(which='minor', direction='in', length=7, top=False)
                axs[j, i].tick_params(which='major', width=2, top=False, right=False)
                axs[j, i].bar(
                    results[1] - 3 / 8, results[0]['temperature'], align='center', width=1 / 4,
                    alpha=.75,
                    color=colors['temperature']
                )
                axs[j, i].bar(
                    results[1] - 1 / 8, results[0]['weather'], align='center', width=1 / 4,
                    alpha=.75,
                    color=colors['weather']
                )
                axs[j, i].bar(
                    results[1] + 1 / 8, results[0]['sun_location'], width=1 / 4, align='center',
                    alpha=.75, color=colors['sun_location']
                )
                axs[j, i].bar(
                    results[1] + 3 / 8, results[0]['random'], align='center', width=1 / 4,
                    alpha=.75,
                    color=colors['random']
                )
                axs[j, i].bar(
                    results[1], results[0]['total'], align='center', width=1, alpha=.45,
                    ls='dashed', color=colors['total'], edgecolor='black'
                )
                axs[j, i].set_title(WEATHER_STATES[state]['name'])
                i += 1
                if i >= 3:
                    j += 1
                    i = 0
            fig.canvas.draw_idle()

        return update

    slider_temp.on_changed(_wrap_update('current_temp'))
    slider_min_temp.on_changed(_wrap_update('min_value'))
    slider_avg_temp.on_changed(_wrap_update('avg_value'))
    slider_max_temp.on_changed(_wrap_update('max_value'))
    slider_sun.on_changed(_wrap_update('sun_value'))
    _wrap_update('current_temp')(current_temp)

    handles = [plt.Rectangle((50, 50), 5, 5, color=colors[label]) for label in labels]
    plt.legend(handles, labels, loc=(0, 8), mode='expand', ncol=5)
    plt.show()


def general_test(
        min_temp: float = 0,
        avg_temp: float = 20,
        max_temp: float = 35,
        current_temp: float = 12,
        weather_state: str = 'c',
        sun_value: float = 50,
        version: int = 2,
        count: int = 100,
        **kwargs
):
    sim = BoktaiSim(
        version=version,
        manual_data=WeatherInfo(
            state='N/A',
            city='N/A',
            latlong='manual',
            woeid='0',
            min_temp=min_temp,
            max_temp=max_temp,
            current_temp=current_temp,
            visibility=5,
            weather_state=weather_state,
            sunrise='2021-06-20T04:19:57.380989-08:00',
            sunset='2021-06-20T23:42:08.855441-08:00',
            timestamp='2021-06-20T22:32:22.441253-08:00',
            manual=True,
            avg_temp=avg_temp
        )
    )

    i = 0
    results = {
        'temperature': {},
        'weather': {},
        'sun_location': {},
        'random': {},
        'total': {}
    }
    for value_type in ('temperature', 'weather', 'sun_location', 'random', 'total'):
        for j in range(0, 11):
            results[value_type][j] = 0
    while i < count:
        values = {
            'temperature': sim.temperature_value,
            'weather': sim.weather_value,
            'sun_location': sim._calulate_sun_value(sun_value, **kwargs),
            'random': sim.random_weather_value
        }
        total = (values['temperature'] * 20) + (values['weather'] * 25) + (values['random'] * 25) + (values[
            'sun_location'] * 30)
        result = total / 100
        if weather_state in ('h', 't'):
            result -= 2
            if result < 0:
                result = 0
        if weather_state in ('hr', 'hc'):
            result -= 1
            if result < 0:
                result = 0
        if weather_state in ('lc', 's', 'c'):
            result += 1
            if result > 10:
                result = 10
        values['total'] = result
        for value_type in ('temperature', 'weather', 'sun_location', 'random', 'total'):
            results[value_type][round(values[value_type])] += 1
        i += 1
    y_pos = np.arange(11)

    dist = {}
    for value_type in ('temperature', 'weather', 'sun_location', 'random', 'total'):
        dist[value_type] = []
        for i in range(0, 11):
            if i in results[value_type]:
                dist[value_type].append(results[value_type][i])
            else:
                dist[value_type].append(0)

    return dist, y_pos


def sun_curve_test(sun_value: float = 50, count: int = 100, **kwargs):
    sim = BoktaiSim(
        version=2,
        manual_data=WeatherInfo(
            state='N/A',
            city='N/A',
            latlong='manual',
            woeid='0',
            min_temp=0,
            max_temp=35,
            current_temp=12,
            visibility=5,
            weather_state='c',
            sunrise='2021-06-20T04:19:57.380989-08:00',
            sunset='2021-06-20T23:42:08.855441-08:00',
            timestamp='2021-06-20T22:32:22.441253-08:00',
            manual=True,
            avg_temp=20
        )
    )

    i = 0
    results = {}
    while i < count:
        result = round(sim._calulate_sun_value(sun_value, **kwargs))
        if result not in results:
            results[result] = 1
        else:
            results[result] += 1
        i += 1
    dist = []
    for i in range(0, 11):
        if i in results:
            dist.append(results[i])
        else:
            dist.append(0)

    objects = tuple(range(0, 11))
    y_pos = np.arange(len(objects))
    return dist, y_pos


def location_value_test(zipcode: int, count: int = 100, lunar_mode: bool = False, **kwargs):
    sim = BoktaiSim(version=2, zipcode=zipcode, lunar_mode=lunar_mode)
    i = 0
    results = {}
    while i < count:
        result = sim.value
        if result not in results:
            results[result] = 1
        else:
            results[result] += 1
        i += 1
    print(results)
    dist = []
    for i in range(0, 11):
        if i in results:
            dist.append(results[i])
        else:
            dist.append(0)
    print(dist)

    objects = tuple(range(0, 11))
    y_pos = np.arange(len(objects))

    plt.bar(y_pos, dist, align='center', alpha=0.5)
    plt.xticks(y_pos, tuple(range(0, 11)))
    plt.ylabel('Occurrence')
    plt.title(f'BoktaiSim Value distribution\nLocation: {zipcode}, Lunar: {lunar_mode}\n'
              f'Weather: {WEATHER_STATES[sim.weather.weather_state]["name"]}\n'
              f'Min: {sim.weather.min_temp_f}, Current: {sim.weather.current_temp_f}, Max: '
              f'{sim.weather.max_temp_f}')

    plt.show()
