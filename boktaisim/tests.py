#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest

from .classes import BoktaiSim, WeatherInfo
from .constants import WEATHER_STATES

import numpy as np
import matplotlib.pyplot as plt


def comprehensive_test():
    fig, axs = plt.subplots(2, 2)
    axs[0, 0].plot(x, y)
    axs[0, 0].set_title("main")
    axs[1, 0].plot(x, y ** 2)
    axs[1, 0].set_title("shares x with main")
    axs[1, 0].sharex(axs[0, 0])
    axs[0, 1].plot(x + 1, y + 1)
    axs[0, 1].set_title("unrelated")
    axs[1, 1].plot(x + 2, y + 2)
    axs[1, 1].set_title("also unrelated")
    fig.tight_layout()


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

    fig, axs = plt.subplots(2, 2)

    axs[0, 0].bar(y_pos, dist, align='center', alpha=0.5)
    #axs[0, 0].xticks(y_pos, objects)
    axs[0, 0].set_title("main")
    axs[1, 0].bar(y_pos, dist, align='center', alpha=0.5)
    #axs[1, 0].xticks(y_pos, objects)
    axs[1, 0].set_title("shares x with main")
    axs[0, 1].bar(y_pos, dist, align='center', alpha=0.5)
    #axs[0, 1].xticks(y_pos, objects)
    axs[0, 1].set_title("unrelated")
    axs[1, 1].bar(y_pos, dist, align='center', alpha=0.5)
    #axs[1, 1].xticks(y_pos, objects)
    axs[1, 1].set_title("also unrelated")
    fig.tight_layout()

    #plt.bar(y_pos, dist, align='center', alpha=0.5)
    #plt.xticks(y_pos, objects)
    #plt.ylabel('Occurrence')
    #plt.title('Value distribution')

    plt.show()


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
    plt.xticks(y_pos, objects)
    plt.ylabel('Occurrence')
    plt.title(f'BoktaiSim Value distribution\nLocation: {zipcode}, Lunar: {lunar_mode}\n'
              f'Weather: {WEATHER_STATES[sim.weather.weather_state]["name"]}\n'
              f'Min: {sim.weather.min_temp_f}, Current: {sim.weather.current_temp_f}, Max: '
              f'{sim.weather.max_temp_f}')

    plt.show()
