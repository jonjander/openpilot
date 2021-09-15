#!/usr/bin/env python3
import math

from cereal import car
from opendbc.can.parser import CANParser
from selfdrive.car.interfaces import RadarInterfaceBase
from selfdrive.car.hyundai.values import DBC

RADAR_START_ADDR = 0x500
RADAR_MSG_COUNT = 32


def get_radar_can_parser(CP):
  if DBC[CP.carFingerprint]['radar'] is None:
    return None

  signals = []
  checks = []

  for addr in range(RADAR_START_ADDR, RADAR_START_ADDR + RADAR_MSG_COUNT):
    msg = f"R_{hex(addr)}"
    signals += [
      ("STATE", msg, 0),
      ("AZIMUTH", msg, 0),
      ("LONG_DIST", msg, 0),
      ("REL_ACCEL", msg, 0),
      ("REL_SPEED", msg, 0),
    ]
    checks += [(msg, 50)]
  return CANParser(DBC[CP.carFingerprint]['radar'], signals, checks, 1)


class RadarInterface(RadarInterfaceBase):
  def __init__(self, CP):
    super().__init__(CP)
    self.updated_messages = set()
    self.trigger_msg = RADAR_START_ADDR + RADAR_MSG_COUNT - 1
    self.track_id = 0

    self.radar_off_can = CP.radarOffCan
    self.rcp = get_radar_can_parser(CP)

  def update(self, can_strings):
    if self.radar_off_can or (self.rcp is None):
      return super().update(None)

    vls = self.rcp.update_strings(can_strings)
    self.updated_messages.update(vls)

    if self.trigger_msg not in self.updated_messages:
      return None

    rr = self._update(self.updated_messages)
    self.updated_messages.clear()

    return rr

  def _update(self, updated_messages):
    ret = car.RadarData.new_message()
    if self.rcp is None:
      return ret

    cpt = self.rcp.vl
    errors = []

    if not self.rcp.can_valid:
      errors.append("canError")
    ret.errors = errors

    for addr in range(0x500, 0x500 + 32):
      msg = f"R_{hex(addr)}"

      if addr not in self.pts:
        self.pts[addr] = car.RadarData.RadarPoint.new_message()
        self.pts[addr].trackId = self.track_id
        self.track_id += 1

      valid = cpt[msg]['STATE'] == 3
      if valid:
        self.pts[addr].measured = True
        self.pts[addr].dRel = cpt[msg]['LONG_DIST']
        self.pts[addr].yRel = 0.5 * -math.sin(math.radians(cpt[msg]['AZIMUTH'])) * cpt[msg]['LONG_DIST']
        self.pts[addr].vRel = cpt[msg]['REL_SPEED']
        self.pts[addr].aRel = cpt[msg]['REL_ACCEL'] 
        self.pts[addr].yvRel = float('nan')

      else:
        del self.pts[addr]

    ret.points = list(self.pts.values())
    return ret
