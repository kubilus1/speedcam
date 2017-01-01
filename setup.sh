#!/bin/sh

v4l2-ctl -c rotate=270
v4l2-ctl -c iso_sensitivity_auto=0
v4l2-ctl -c iso_sensitivity=4
v4l2-ctl -c power_line_frequency=2
v4l2-ctl -c exposure_dynamic_framerate=0
v4l2-ctl -c saturation=40
v4l2-ctl -c auto_exposure_bias=14
v4l2-ctl -c exposure_metering_mode=1
v4l2-ctl -c white_balance_auto_preset=1
v4l2-ctl -p 30
