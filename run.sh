#!/bin/bash
/usr/bin/env python3 -m src.cli.main --token $(cat TOKEN) $@ 2>&1 | tee session.log
