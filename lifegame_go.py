#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""In-house Contest 2016: Lifegame GO (C) 2016 Fixstars Corp."""
import sys
import os
import curses
import time
import subprocess
import threading
import shlex
import random
import math
import collections
import signal
import numpy as np
VERSION = "0.14"
REVISION = "a"
VER_DATE = "20161027"
VISIBLE = False
TIME_LIMIT = 5.0
def signal_handler(signum, frame):
	global VISIBLE
	if VISIBLE:
		curses.nocbreak()
		curses.echo()
		curses.endwin()
	sys.exit()
def bitcount(bits):
	bits = (bits & 0x55555555) + (bits >> 1 & 0x55555555)
	bits = (bits & 0x33333333) + (bits >> 2 & 0x33333333)
	bits = (bits & 0x0f0f0f0f) + (bits >> 4 & 0x0f0f0f0f)
	bits = (bits & 0x00ff00ff) + (bits >> 8 & 0x00ff00ff)
	return (bits & 0x0000ffff) + (bits >>16 & 0x0000ffff)
def read_response(player, player_time):
	start_time = time.time()
	class ExecThread(threading.Thread):
		def __init__(self, player):
			self.player = player
			self.response = None
			threading.Thread.__init__(self)
		def run(self):
			self.response = self.player.stdout.readline().strip()
		def get_response(self):
			return self.response
	t = ExecThread(player)
	t.setDaemon(True)
	t.start()
	if t.isAlive(): t.join(player_time)
	player_time -= time.time() - start_time
	return t.get_response(), player_time

def check_TLE(players, name, player_time):
	if player_time <= 0.0:
		print >>sys.stderr, "Error: time limit exceeded: %s" % (name,)
		return True
	return False
def quit_game(players, player_times):
	for idx in range(2):
		try:
			players[idx].stdin.write("quit¥n")
			players[idx].stdin.flush()
			response, player_times[idx] = read_response(players[idx], player_times[idx])
		except:
			pass
class LifegameGo:
	def __init__(self, player_data, R=10, C=10, visible=True, wait_time=30):
		global VISIBLE
		self.player_data = player_data
		self.names = [name for name, command in self.player_data]
		self.num_init_active_cells = 20
		self.R = R
		self.C = C
		VISIBLE = self.visible = visible
		self.wait_time = wait_time
		self.C5 = ((self.C-1) >> 5) + 1
		self.RCinv = 1.0 / (self.R * self.C)
		self.remain_bits = ((~self.C + 1) & 0x1f) * self.R
		self.log4inv = 1.0 / math.log(4.0)
		self.cells = [[0 for c in range(self.C5)] for r in range(self.R)]
		self.players = [[0 for c in range(self.C)] for r in range(self.R)]
		self.modR = [i % self.R for i in range(self.R * 3)]
		self.modC = [i % self.C for i in range(self.C * 3)]
		# 0: death, 1: change, 2: birth, 3: survival
		# Conway's Game of Life
		self.rules = [[[0, 0, 3, 2, 0, 0, 0, 0, 0] for c in range(self.C)] for r in range(self.R)]
		self.rate = 0.3
		self.cnt = [[0 for c in range(self.C)] for r in range(self.R)]
		self.rule_bits = [[0 for c in range(self.C5)] for r in range(4)]
		self.entropy = 1.0
		self.patterns = [0, 0, 0, 0]
		self.step = 0
		self.messages = []
		if self.visible:
			self.stdscr = curses.initscr()
			self.my, self.mx = self.stdscr.getmaxyx()
			self.pminrow = 0
			self.pmincol = 0
			self.sminrow = 2
			self.smincol = 2
			self.smaxrow = self.my - 1
			self.smaxcol = self.mx - 1
			curses.start_color()
			curses.noecho()
			curses.cbreak()
			self.stdscr.keypad(1)
			curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
			curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
			curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
			self.pad = curses.newpad(self.R + 2, self.C + 2)
			self.pad.border()
			self.stdscr.addstr(1, 3, "Step: %d | %s [o]: %d | %s [x]: %d | entropy: %.5f" % (self.step, self.names[0], 0, self.names[1], 0, self.entropy))
			self.stdscr.refresh()
	def initialize(self):
		### for Linux
		#players = [subprocess.Popen(shlex.split(command), shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE) for name, command in self.player_data]
		### for Linux/Windows
		players = [subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE) for name, command in self.player_data]
		player_times = [TIME_LIMIT for i in range(2)]
		for idx in range(2):
			players[idx].stdin.write("init %s %d %s %d %d¥n" % (self.names[idx], idx + 1, self.names[idx^1], self.R, self.C))
			players[idx].stdin.flush()
			response, player_times[idx] = read_response(players[idx], player_times[idx])
		self.dominant_players = [[0 for c in range(self.C)] for r in range(self.R)]
		self.dominant_cnt = [0 for i in range(3)] # non-player, 1st-player, 2nd-player
		active_cells = []
		for turn in range(self.num_init_active_cells): # each 20 active cells for players
			for idx in range(2):
				try:
					players[idx].stdin.write("play %s¥n" % " ".join(map(str, active_cells)))
					players[idx].stdin.flush()
					response, player_times[idx] = read_response(players[idx], player_times[idx])
					if check_TLE(players, self.names[idx], player_times[idx]):
						winner = idx^1
						msg = "%s's program got time limit exceeded." % self.names[idx]
						tle_player = (idx, self.names[idx])
						quit_game(players, player_times)
						return self.names[winner], msg
					x, y = map(int, response.split())
					if self.check_cell(x, y):
						raise Exception("same cell is incorrect")
					if x < 0 or x >= self.R or y < 0 or y >= self.C:
						raise Exception("invalid cell position: (%d, %d)" % (x, y))
					self.cells[x][y>>5] |= 1 << (y & 0x1f)
					self.players[x][y] = idx + 1
					self.dominant_cnt[self.dominant_players[x][y]] += 1
					active_cells.extend([x, y])
				except Exception as e:
					winner = idx^1
					msg = "%s's program was stopped in the play command: %s" % (self.names[idx], str(e))
					quit_game(players, player_times)
					return self.names[winner], msg
		self.update_dominant(self.update_count())
		quit_game(players, player_times)
		return None, None
	def finish(self):
		if self.visible:
			curses.nocbreak()
			self.stdscr.keypad(0)
			curses.echo()
			curses.endwin()
			print "¥n".join(self.messages)
	def check_cell(self, x, y):
		return self.cells[x][y>>5] & 1 << (y & 0x1f)
	def update_count(self):
		for i in range(self.R):
			for j in range(self.C):
				self.cnt[i][j] = 0
		cnt_players = [[np.zeros(2, dtype=np.int) for y in range(self.C)] for x in range(self.R)]
		for x in range(self.R):
			for y in range(self.C):
				if self.check_cell(x, y):
					player = np.array([1, 0] if self.players[x][y] == 1 else [0, 1])
					for i in range(-1, 2):
						for j in range(-1, 2):
							if i != 0 or j != 0:
								self.cnt[self.modR[x+i+self.R]][self.modC[y+j+self.C]] += 1
								cnt_players[self.modR[x+i+self.R]][self.modC[y+j+self.C]] += player
		return cnt_players

	def update_dominant(self, cnt_players):
		for i in range(3): self.dominant_cnt[i] = 0
		for x in range(self.R):
			for y in range(self.C):
				if self.players[x][y] != 0:
					self.dominant_players[x][y] = self.players[x][y]
				elif cnt_players[x][y][0] == cnt_players[x][y][1]:
					self.dominant_players[x][y] = 0
				else:
					self.dominant_players[x][y] = 1 if cnt_players[x][y][0] > cnt_players[x][y][1] else 2
				self.dominant_cnt[self.dominant_players[x][y]] += 1
	def next(self):
		for i in range(4): self.patterns[i] = 0
		for x in range(self.R):
			for i in range(4):
				for j in range(self.C5):
					self.rule_bits[i][j] = 0
			for y in range(self.C):
				self.rule_bits[self.rules[x][y][self.cnt[x][y]]][y>>5] |= 1 << (y & 0x1f)
			for i in range(self.C5):
				self.cellBits = self.cells[x][i]
				self.cells[x][i] = self.cells[x][i] & ~self.rule_bits[0][i] ^ self.rule_bits[1][i] | self.rule_bits[2][i]
				self.patterns[0] += bitcount(~self.cellBits & ~self.cells[x][i])
				self.patterns[1] += bitcount(self.cellBits & ~self.cells[x][i])
				self.patterns[2] += bitcount(~self.cellBits & self.cells[x][i])
				self.patterns[3] += bitcount(self.cellBits & self.cells[x][i])
		self.remain_bits
		self.entropy = 0.0
		for i in range(4):
			if self.patterns[i] == 0: continue
			p = self.patterns[i] * self.RCinv
			self.entropy -= p * math.log(p) * self.log4inv
		for x in range(self.R):
			for y in range(self.C):
				self.players[x][y] = self.dominant_players[x][y] if self.check_cell(x, y) else 0
		self.update_dominant(self.update_count())
		self.step += 1
	def count_alive(self):
		cnt = 0
		for x in range(self.R):
			for c in range(self.C5):
				cnt += bitcount(self.cells[x][c])
			return cnt
	def pause(self):
		if self.visible:
			self.pad.getch()
	def show(self, target="player"):
		p0, p1, p2 = self.dominant_cnt
		if self.visible:
			field = ""
			p1c, p2c = 0, 0
			for i in range(self.R):
				line = "".join([("_", "o", "x")[self.players[i][j]] for j in range(self.C)])
				p1c += line.count("o")
				p2c += line.count("x")
				field += ";%s¥n" % line
			msg = "Step: %d | %s [o]: %d (%d) | %s [x]: %d (%d) | entropy: %.5f" % (self.step, self.names[0], p1, p1c, self.names[1], p2, p2c, self.entropy)
			self.messages.append(field + msg)
			self.stdscr.addstr(1, 3, msg)
			self.stdscr.refresh()
			for i in range(self.R):
				for j in range(self.C):
					if target == "player":
						self.pad.addstr(i + 1, j + 1, (" ", "o", "x")[self.players[i][j]], curses.color_pair(self.players[i][j] + 1))
					if target == "dominant":
						self.pad.addstr(i + 1, j + 1, (" ", "o", "x")[self.dominant_players[i][j]], curses.color_pair(self.players[i][j] + 1))
					elif target == "count":
						self.pad.addstr(i + 1, j + 1, ("%d" % self.cnt[i][j] if self.cnt[i][j] else " "), curses.color_pair(self.dominant_players[i][j] + 1))
					self.pad.refresh(self.pminrow, self.pmincol, self.sminrow, self.smincol, self.smaxrow, self.smaxcol)
			curses.delay_output(self.wait_time)
		else:
			p1c, p2c = 0, 0
			for i in range(self.R):
				line = "".join([("_", "o", "x")[self.players[i][j]] for j in range(self.C)])
				p1c += line.count("o")
				p2c += line.count("x")
				print ";%s" % line
			print "Step: %d | %s [o]: %d (%d) | %s [x]: %d (%d) | entropy: %.5f" % (self.step, self.names[0], p1, p1c, self.names[1], p2, p2c, self.entropy)
	def result(self):
		p0, p1, p2 = self.dominant_cnt
		if p1 != p2:
			print "#Winner: %s" % self.names[0 if p1 > p2 else 1]
		else:
			print "#Draw"
	def main(args):
		if len(args) < 5:
			print >>sys.stderr, "Usage: %s name1 command1 name2 command2 [nsteps=3] [R=10] [C=10] [target=dominant] [wait_time=1000]" % os.path.basename(args[0])
			print >>sys.stderr, " name1 : first player's name"
			print >>sys.stderr, " command1 : first player's command"
			print >>sys.stderr, " name2 : second player's name"
			print >>sys.stderr, " command2 : second player's command"
			print >>sys.stderr, " nsteps : number of steps for the cellular automaton [default: 3]"
			print >>sys.stderr, " R : number of rows (y-axis) [default: 10]"
			print >>sys.stderr, " C : number of columns (x-asis) [default: 10]"
			print >>sys.stderr, " target : type of the result: player, dominant, count, novis [default: dominant]"
			print >>sys.stderr, " player : for 2-players' cells alive"
			print >>sys.stderr, " dominant : for 2-players' dominant cells"
			print >>sys.stderr, " count : for number of 2-players' cells"
			print >>sys.stderr, " novis : No curses"
			print >>sys.stderr, " wait_time: wait time for curses (milli-seconds) [default: 1000]"
			sys.exit(1)
		signal.signal(signal.SIGINT, signal_handler)
		player_data = [(name, command) for name, command in zip(args[1:4:2], args[2:5:2])]
		nsteps = int(args[5]) if len(args) > 5 else 3
		R = int(args[6]) if len(args) > 6 else 10
		C = int(args[7]) if len(args) > 7 else 10
		# targets: "player", "dominant", "count", "novis"
		target = args[8].lower() if len(args) > 8 else "dominant"
		visible = False if target == "novis" else True
		wait_time = int(args[9]) if len(args) > 9 else 1000
		if target not in ("player", "dominant", "count", "novis"):
			print >>sys.stderr, "Error: unknown target: %s" % target
			sys.exit(1)
		print "nsteps=%d, R=%d, C=%d, target=%s" % (nsteps, R, C, target)
		lg = LifegameGo(player_data, R, C, visible, wait_time)
		winner, msg = lg.initialize()
		if winner:
			print msg
			print "#Winner: %s" % winner
		else:
			lg.show(target)
			for i in range(nsteps):
				lg.next()
				lg.show(target)
			lg.pause()
			lg.finish()
			lg.result()
if __name__ == "__main__": main(sys.argv)
