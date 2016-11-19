#include <iostream>
#include <sstream>
#include <fstream>
#include <vector>
#include <map>
#include <tuple>
#include <algorithm>
#include <random>
#include <string>
#include <cmath>
#include <cstring>
#include <sys/stat.h>

using namespace std;

unsigned long bitcount(unsigned long bits)
{
	bits = (bits & 0x55555555) + (bits >> 1 & 0x55555555);
	bits = (bits & 0x33333333) + (bits >> 2 & 0x33333333);
	bits = (bits & 0x0f0f0f0f) + (bits >> 4 & 0x0f0f0f0f);
	bits = (bits & 0x00ff00ff) + (bits >> 8 & 0x00ff00ff);
	return (bits & 0x0000ffff) + (bits >>16 & 0x0000ffff);
}

class LifegameGo {
private:
	int R;
	int C;
	int C5;
	int RCinv;
	int remain_bits;
	double log4inv;
	vector<vector<int > > cells;
	vector<vector<int > > players;
	vector<int > modR;
	vector<int > modC;
	vector<vector<vector<int > > > rules;
	double rate;
	vector<vector<int > > cnt;
	vector<vector<int > > rule_bits;
	double entropy;
	vector<int > patterns;
	int step;
	vector<vector<int > > dominant_players;
	vector<int > dominant_cnt;

public:
	LifegameGo(int R, int C) : R(R), C(C) {
		C5 = ((C-1) >> 5) + 1;
		RCinv = 1.0 / (R * C);
		remain_bits = ((~C + 1) & 0x1f) * R;
		log4inv = 1.0 / log(4.0);
		cells.assign(R, vector<int >(C5, 0));
		players.assign(R, vector<int >(C, 0));
		for (int i = 0; i < R * 3; i++) modR.push_back(i % R);
		for (int i = 0; i < C * 3; i++) modC.push_back(i % C);
		rules.assign(R, vector<vector<int > >(C, vector<int >({0, 0, 3, 2, 0, 0, 0, 0, 0})));
		rate = 0.3;
		cnt.assign(R, vector<int >(C, 0));
		rule_bits.assign(4, vector<int >(C5, 0));
		entropy = 1.0;
		patterns.assign(4, 0);
		step = 0;
		dominant_players.assign(R, vector<int >(C, 0));
		dominant_cnt.assign({0, 0, 0});
	}

	~LifegameGo() {
	}

	int check_cell(int x, int y) {
		return cells[x][y>>5] & 1 << (y & 0x1f);
	}

	vector<vector<vector<int > > > update_count() {
		for (int i = 0; i < R; i++)
			for (int j = 0; j < C; j++)
				cnt[i][j] = 0;
		vector<vector<vector<int > > > cnt_players(R, vector<vector<int > >(C, vector<int >(2, 0)));
for (int x = 0; x < R; x++) {
for (int y = 0; y < C; y++) {
if (check_cell(x, y)) {
vector<int > player(2, 0);
if (players[x][y] == 1) player[0] = 1;
else player[1] = 1;
for (int i = -1; i <= 1; i++) {
for (int j = -1; j <= 1; j++) {
if (i != 0 || j != 0) {
cnt[modR[x+i+R]][modC[y+j+C]] += 1;
for (int k = 0; k < 2; k++)
cnt_players[modR[x+i+R]][modC[y+j+C]][k] += player[k];
}
}
}
}
}
}
return cnt_players;
}
void update_dominant(const vector<vector<vector<int > > >& cnt_players) {
for (int i = 0; i < 3; i++) dominant_cnt[i] = 0;
for (int x = 0; x < R; x++) {
for (int y = 0; y < C; y++) {
if (players[x][y] != 0)
dominant_players[x][y] = players[x][y];
else if (cnt_players[x][y][0] == cnt_players[x][y][1])
dominant_players[x][y] = 0;
else
dominant_players[x][y] = cnt_players[x][y][0] > cnt_players[x][y][1] ? 1 : 2;
dominant_cnt[dominant_players[x][y]] += 1;
}
}
}
void next() {
for (int i = 0; i < 4; i++) patterns[i] = 0;
for (int x = 0; x < R; x++) {
for (int i = 0; i < 4; i++) {
for (int j = 0; j < C5; j++) {
rule_bits[i][j] = 0;
}
}
for (int y = 0; y < C; y++) {
rule_bits[rules[x][y][cnt[x][y]]][y>>5] |= 1 << (y & 0x1f);
}
for (int i = 0; i < C5; i++) {
int cellBits = cells[x][i];
cells[x][i] = cells[x][i] & ~rule_bits[0][i] ^ rule_bits[1][i] | rule_bits[2][i];
patterns[0] += bitcount(~cellBits & ~cells[x][i]);
patterns[1] += bitcount(cellBits & ~cells[x][i]);
patterns[2] += bitcount(~cellBits & cells[x][i]);
patterns[3] += bitcount(cellBits & cells[x][i]);
}
}
patterns[0] -= remain_bits;
entropy = 0.0;
for (int i = 0; i < 4; i++) {
if (patterns[i] == 0) continue;
double p = patterns[i] * RCinv;
entropy -= p * log(p) * log4inv;
}
for (int x = 0; x < R; x++)
for (int y = 0; y < C; y++)
players[x][y] = check_cell(x, y) ? dominant_players[x][y] : 0;
update_dominant(update_count());
step++;
}
int count_alive() {
int cnt = 0;
for (int x = 0; x < R; x++)
for (int c = 0; c < C5; c++)
cnt += bitcount(cells[x][c]);
return cnt;
}
void set_cells(const vector<pair<int, int > >& all_pos) {
int idx = 0;
for (const auto& pos : all_pos) {
int x = pos.first;
int y = pos.second;
cells[x][y>>5] |= 1 << (y & 0x1f);
players[x][y] = idx + 1;
dominant_cnt[dominant_players[x][y]]++;
idx ^= 1;
}
}
void set_cell(const pair<int, int>& pos, int idx) {
int x = pos.first;
int y = pos.second;
cells[x][y>>5] |= 1 << (y & 0x1f);
players[x][y] = idx + 1;
dominant_cnt[dominant_players[x][y]]++;
}
void run(int nstep) {
for (int i = 0; i < nstep; i++) next();
}
pair<int, int> score() {
return make_pair(dominant_cnt[1], dominant_cnt[2]);
}
};
int main()
{
ios_base::sync_with_stdio(false);
string name, opp_name;
int idx;
string str;
stringstream ss;
char s[256];
vector<string> data;
int R = 10;
int C = 10;
// initialize
for (;;) {
getline(cin, str);
copy(str.c_str(), str.c_str() + str.size() + 1, s);
data.clear();
for (char* p = strtok(s, " "); p; p = strtok(nullptr, " ")) data.push_back(p);
string status(data[0]);
if (status == "init") {
name = data[1];
idx = stoi(data[2]);
opp_name = data[3];
R = stoi(data[4]);
C = stoi(data[5]);
cout << endl << flush;
break;
}
}
// play a game
for (;;) {
getline(cin, str);
copy(str.c_str(), str.c_str() + str.size() + 1, s);
data.clear();
for (char* p = strtok(s, " "); p; p = strtok(nullptr, " ")) data.push_back(p);
string status(data[0]);
if (status == "play") {
vector<pair<int, int > > all_pos;
for (int i = 1; i < data.size(); i += 2)
all_pos.push_back(make_pair(stol(data[i]), stol(data[i+1])));
pair<int, pair<int, int > > best_pos(-1000, make_pair(-1, -1));
for (int r = 0; r < R; r++) {
for (int c = 0; c < C; c++) {
pair<int, int> pos(r, c);
if (find(all_pos.begin(), all_pos.end(), pos) != all_pos.end()) continue;
LifegameGo lg(R, C);
lg.set_cells(all_pos);
lg.set_cell(pos, idx - 1);
lg.update_dominant(lg.update_count());
lg.run(3);
pair<int, int> score = lg.score();
int estimate = (idx == 1 ? score.first - score.second : score.second - score.first);
if (best_pos.first < estimate) best_pos = make_pair(estimate, pos);
}
}
cout << best_pos.second.first << " " << best_pos.second.second << endl << flush;
} else if (status == "quit") {
cout << endl << flush;
break;
}
}
return 0;
}