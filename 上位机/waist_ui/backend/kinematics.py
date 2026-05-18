# coding: utf-8
import math


class Kinematics:
    def __init__(self):
        self.b_l = [[0.0] * 4 for _ in range(5)]
        self.p_m = [[0.0] * 4 for _ in range(5)]
        self.b_m = [[0.0] * 4 for _ in range(5)]
        self.R = [[0.0] * 4 for _ in range(4)]
        self.sp_coor = [0.0] * 4
        self.L = [0.0] * 5

        self.set_param(30, 16.5, 25.5)
        self.cal_point()

    def set_param(self, bl, l_min, l_max):
        self.Bl = bl
        self.Bw = 10
        self.Pl = 1.05 * bl
        self.Pw = 15
        self.l_min = l_min
        self.l_max = l_max

    def cal_point(self):
        self.b_l[1][1], self.b_l[1][2], self.b_l[1][3] = -self.Bl / 2,  self.Bw / 2, 0
        self.b_l[2][1], self.b_l[2][2], self.b_l[2][3] = -self.Bl / 2, -self.Bw / 2, 0
        self.b_l[3][1], self.b_l[3][2], self.b_l[3][3] =  self.Bl / 2, -self.Bw / 2, 0
        self.b_l[4][1], self.b_l[4][2], self.b_l[4][3] =  self.Bl / 2,  self.Bw / 2, 0

        self.p_m[1][1], self.p_m[1][2], self.p_m[1][3] = -self.Pl / 2,  self.Pw / 2, 0
        self.p_m[2][1], self.p_m[2][2], self.p_m[2][3] = -self.Pl / 2, -self.Pw / 2, 0
        self.p_m[3][1], self.p_m[3][2], self.p_m[3][3] =  self.Pl / 2, -self.Pw / 2, 0
        self.p_m[4][1], self.p_m[4][2], self.p_m[4][3] =  self.Pl / 2,  self.Pw / 2, 0

    def cal_r_sp(self, alpha, beta, gamma):
        self.R[1][1] = math.cos(alpha) * math.cos(beta)
        self.R[1][2] = math.cos(alpha) * math.sin(beta) * math.sin(gamma) - math.sin(alpha) * math.cos(gamma)
        self.R[1][3] = math.cos(alpha) * math.sin(beta) * math.cos(gamma) + math.sin(alpha) * math.sin(gamma)

        self.R[2][1] = math.sin(alpha) * math.cos(beta)
        self.R[2][2] = -math.sin(alpha) * math.sin(beta) * math.sin(gamma) + math.cos(alpha) * math.cos(gamma)
        self.R[2][3] = -math.sin(alpha) * math.sin(beta) * math.cos(gamma) - math.cos(alpha) * math.sin(gamma)

        self.R[3][1] = -math.sin(beta)
        self.R[3][2] = math.cos(beta) * math.sin(gamma)
        self.R[3][3] = math.cos(beta) * math.cos(gamma)

        m_1 = math.sqrt((self.Pl * 0.5) ** 2 + (self.Pw * 0.5) ** 2) - \
              math.sqrt((self.Bl * 0.5) ** 2 + (self.Bw * 0.5) ** 2)

        self.sp = math.sqrt(21.5 ** 2 - m_1 ** 2)

        self.sp_coor[1] = self.sp * math.sin(beta)
        self.sp_coor[2] = -self.sp * math.sin(gamma) * math.cos(beta)
        self.sp_coor[3] = self.sp * math.cos(gamma) * math.cos(beta)

    def cal_L(self, flag):
        for i in range(1, 5):
            self.b_m[i][1] = self.R[1][1] * self.p_m[i][1] + self.R[1][2] * self.p_m[i][2] + self.sp_coor[1]
            self.b_m[i][2] = self.R[2][1] * self.p_m[i][1] + self.R[2][2] * self.p_m[i][2] + self.sp_coor[2]
            self.b_m[i][3] = self.R[3][1] * self.p_m[i][1] + self.R[3][2] * self.p_m[i][2] + self.sp_coor[3]

            self.L[i] = math.sqrt(
                (self.b_m[i][1] - self.b_l[i][1]) ** 2 +
                (self.b_m[i][2] - self.b_l[i][2]) ** 2 +
                (self.b_m[i][3] - self.b_l[i][3]) ** 2
            )

            if flag:
                self.L[i] = 4096 * (self.L[i] - self.l_min) / 10

    def reversed_solution(self, alpha, beta, gamma):
        a = math.radians(alpha)
        b = math.radians(beta)
        g = math.radians(gamma)
        self.cal_r_sp(a, b, g)
        self.cal_L(1)

    def identify(self, action_data):
        left_1 = [
            action_data[1][0] / 100.0 + self.l_min,
            action_data[1][1] / 100.0 + self.l_min,
            action_data[1][2] / 100.0 + self.l_min,
            action_data[1][3] / 100.0 + self.l_min,
            action_data[1][4] - action_data[0][4]
        ]

        error = [0.0] * 200
        LL = 15.0

        for i in range(1, 200):
            self.set_param(LL, 16.5, 25.5)
            self.cal_point()

            beta = -left_1[4] * 0.48 * math.pi / 180.0
            self.cal_r_sp(0, beta, 0)
            self.cal_L(0)

            error[i] = left_1[0] - self.L[2]
            LL = LL + 0.5 * error[i]

        self.set_param(LL, 16.5, 25.5)
        return LL

    def get_L(self, i):
        return self.L[i]


_L_TO_MOTOR_SCALE = 4096.0 * (25.5 - 16.5) / 10.0


def angles_to_motor_commands(alpha, beta, gamma, kinematics=None):
    if kinematics is None:
        kinematics = Kinematics()
    kinematics.reversed_solution(alpha, beta, gamma)

    def _to_range(v):
        return max(0.0, min(100.0, v * 100.0 / _L_TO_MOTOR_SCALE))

    return {
        'LF': _to_range(kinematics.get_L(1)),
        'LB': _to_range(kinematics.get_L(2)),
        'RB': _to_range(kinematics.get_L(3)),
        'RF': _to_range(kinematics.get_L(4)),
    }