import math
from enum import Enum
import os
import hashlib
import pandas as pd
import yaml
from collections import defaultdict
import numpy as np
from scipy.special import lambertw


class IVDataType(Enum):
    OUTPUT = 0
    TRANSFER = 1
class ComputeService:
    def __init__(self):
        self.data_file_path = ""
        self.md5_dict = {}
        self.DRAIN_I = ""  # 漏极电流列名
        self.DRAIN_V = ""  # 漏极电压列名
        self.GATE_V = ""  # 栅极电压列名
        self.W = ""  # 宽度列名
        self.L = ""  # 长度列名
        self.TYPE = ""  # 类型列名
        self.M_NUM = ""  # M编号列名
        self.D_NUM = ""  # D编号列名
        self.df = None
        self.data_gate_tree = None
        self.data_drain_tree = None
        self.Cox_area = 0.03
        
        # 初始化时加载配置
        self.__load_config()
        self.vc = 0.0
        self.coeffs = None

        self.KB = 8.6173 * 1E-5  # ev/k
        self.q_element = 1.6E-19  # 库伦
        self.eps0 = 8.854187817E-12  # (F/m) F=Q/U=库伦/V
        self.eps_sio2 = 25 * self.eps0  # this is a input value 25 类似wl
        self.eps_s = 15 * self.eps0  # this is a input value 25 类似wl
        self.Cox_area = 0.03  # F/m/m this is a input value 类似wl

        # r_inner = 247#nm

        self.phi_F0 = 0.40  # V

        self.Vfb = -0.8  # V

        self.T = 300  # K

        self.ufree = 0.8  # cm^2/V/S

        self.VT = self.T * self.KB  # this is the phi_free
        self.resis = 0
        self.DIBL_A = 0
        self.DIBL_B = 0
        self.Vy = 0

        self.Nfree = 1  # 1E18  the  concentration of free carriers

        self.Ntail_eff = 1.2  # 1   1.2O
        self.Ndeep_eff = 0.2  # 0.4  0.2

        self.phi_tail = 0.03
        self.phi_deep = 0.05
        self.m = -1
        self.n = -23
        self.M = 0.0

        self.Vc = 0.0
        self.coeffs_list = []

    def load_data_file_path(self,filepath:str)->None:
        md5_dict = self.__collect_excel_md5(filepath)
        self.md5_dict = md5_dict
        self.data_file_path = filepath

        print(self.md5_dict)
        print(self.data_file_path)

        self.__load_config()

    def __get_file_md5(self,file_path: str) -> str:
        """计算文件的MD5值"""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def __collect_excel_md5(self,folder: str) -> dict[str, str]:
        """扫描文件夹下所有 xls/xlsx 文件并返回 {文件名: md5} 字典"""
        result = {}
        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith((".xls", ".xlsx")):
                    full_path = os.path.join(root, file)
                    md5_value = self.__get_file_md5(full_path)
                    result[md5_value] = file
        return result

    def __load_config(self):
        """加载配置文件"""
        yaml_file_path = os.path.join(os.getcwd(), 'cfg.yaml')
        try:
            with open(yaml_file_path, 'r') as yaml_file:
                self.column_names = yaml.safe_load(yaml_file)
        except Exception as e:
            print(f"配置文件加载错误: {str(e)}")
            self._set_default_config()

        # 设置列名别名，简化代码
        self._set_column_aliases()

    def _set_column_aliases(self):
        """设置列名别名，简化代码中的引用"""
        self.DRAIN_I = self.column_names['DrainIName']  # 漏极电流列名
        self.DRAIN_V = self.column_names['DrainVName']  # 漏极电压列名
        self.GATE_V = self.column_names['GateVName']  # 栅极电压列名
        self.W = self.column_names['WName']  # 宽度列名
        self.L = self.column_names['LName']  # 长度列名
        self.TYPE = self.column_names['TOName']  # 类型列名
        self.M_NUM = self.column_names['M_NumName']  # M编号列名
        self.D_NUM = self.column_names['D_NumName']  # D编号列名

    def _set_default_config(self):
        """设置默认配置"""
        self.column_names = {
            'DrainIName': 'DrainI',
            'DrainVName': 'DrainV',
            'GateVName': 'GateV',
            'WName': 'W',
            'LName': 'L',
            'TOName': 'TO',
            'M_NumName': 'M_Num',
            'D_NumName': 'D_Num'
        }
        # 设置列名别名
        self._set_column_aliases()

    def _set_compute_file(self, file_path: str) -> None:
        self.df = pd.read_excel(file_path, sheet_name="Sheet1")
        self.df.columns = self.df.columns.str.strip()
        # 恢复树形结构初始化
        self._build_tree()  # 需要重新启用树形结构构建

    def get_w_index(self, w: float) -> int:
        """获取W值在全局列表中的索引"""
        ws_list = self.get_ws()
        # 使用近似匹配处理浮点数精度问题
        matches = [i for i, val in enumerate(ws_list) if np.isclose(val, w, atol=0.001)]
        return matches[0] if matches else -1

    def get_l_index(self, w: float, l: float) -> int:
        """获取固定W后，L在局部列表中的索引"""
        # 获取当前W对应的所有L值
        mask = np.isclose(self.df[self.W], w, atol=0.001)
        ls_local = self.df[mask][self.L].drop_duplicates().sort_values().astype(float).tolist()
        # 查找近似匹配的索引
        matches = [i for i, val in enumerate(ls_local) if np.isclose(val, l, atol=0.001)]
        return matches[0] if matches else -1
    def _fitting(self,w:float,l:float,data_params,enable_rc=True,max_it = 100,error_tor = 0.01):
        vgs_all = self.get_vgs(w,l)
        self.Rc_V, self.Vd_arry = self.get_Rc(self.get_ws(), self.get_ls(), vgs_all, data_params,enable_rc,max_it,error_tor)
        
        if enable_rc:
            # 只有启用RC时才进行拟合
            self.fit_poly3_2d(self.Rc_V[self.get_w_index(w)][self.get_l_index(w, l)], vgs_all, self.Vd_arry)
            self.fit_quadratic_per_Vg(self.Rc_V[self.get_w_index(w)][self.get_l_index(w, l)], self.Vd_arry)
        else:
            # 禁用RC时，重置拟合系数
            self.coeffs = None
            self.coeffs_list = []
            
        print("fitting 后的coeffs")
        print(self.coeffs)
        print("fitting rc v")
        print(self.Rc_V)
        print("fitting 后的vd array")
        print(self.Vd_arry)


    def reset_fitting_parameters(self):
        """重置拟合相关参数到初始状态"""
        self.Rc_V = None  # 接触电阻数组
        self.Vd_arry = None  # 漏极电压数组
        self.coeffs = None  # 多项式拟合系数
        self.coeffs_list = []  # 二次拟合系数列表

        # 可选：重置其他相关参数
        self.vc = 0.0  # 接触电压
        self.Vc = 0.0
        self.coeffs_list = []
        # self.DIBL_A = 0         # 根据实际需求决定是否重置
        # self.DIBL_B = 0         # 根据实际需求决定是否重置
        self.Rc_V = None
        self.Vd_arry = None


    def fit_quadratic_per_Vg(self,Rc, Vd_list):
        Rc = np.array(Rc)
        Vd_list = np.array(Vd_list, dtype=float)
        for Rc_row in Rc:
            # 拟合一元二次多项式 Rc = a*Vd^2 + b*Vd + c
            coeffs = np.polyfit(Vd_list, Rc_row, deg=3)
            self.coeffs_list.append(coeffs)  # [a, b, c]
        return self.coeffs_list  # 每一项对应一个 Vg 下的拟合系数 [a, b, c]

    def _get_data(self, w: float, l: float, to: float, voltage: float) -> list:
        # 添加类型转换和空值保护
        to = str(to)  # 确保类型与分组时一致
        try:
            if to == "0":  # 传输特性（Transfer）
                return self.data_gate_tree.get(w, {}).get(l, {}).get(to, {}).get(voltage, [])
            else:  # 输出特性（Output）
                return self.data_drain_tree.get(w, {}).get(l, {}).get(to, {}).get(voltage, [])
        except KeyError:
            return []

    def _build_tree(self):
        # 修复分组逻辑和数据结构初始化
        self.data_gate_tree = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
        self.data_drain_tree = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))

        # 检查列名是否正确设置
        required_columns = [self.W, self.L, self.TYPE, self.GATE_V, self.DRAIN_V, self.DRAIN_I]
        
        # 检查列是否存在
        missing_columns = [col for col in required_columns if col not in self.df.columns]
        if missing_columns:
            raise ValueError(f"Missing columns in DataFrame: {missing_columns}. Available columns: {list(self.df.columns)}")

        # 确保分组列顺序和数据类型正确
        try:
            for (w, l, to, gv), group in self.df.groupby([self.W, self.L, self.TYPE, self.GATE_V]):
                self.data_gate_tree[w][l][str(to)][gv] = group[self.DRAIN_I].tolist()

            for (w, l, to, dv), group in self.df.groupby([self.W, self.L, self.TYPE, self.DRAIN_V]):
                self.data_drain_tree[w][l][str(to)][dv] = group[self.DRAIN_I].tolist()
        except Exception as e:
            raise ValueError(f"Error building data tree: {str(e)}. Column names: {dict(zip(['W', 'L', 'TYPE', 'GATE_V', 'DRAIN_V', 'DRAIN_I'], required_columns))}")

    def get_transfer_data(self, w_sel: float, l_sel: float, type_sel: int, vds_sel: float):
        """获取传输特性数据（等效于transfer_computer函数）
        参数:
            w_sel: 器件宽度
            l_sel: 器件长度
            type_sel: 测试类型 (0/1)
            vds_sel: 漏极电压值
        返回:
            (x, y) 元组，包含栅压和漏极电流数据
        """
        # 构建筛选条件
        mask = (
                (self.df[self.W] == w_sel) &
                (self.df[self.L] == l_sel) &
                (self.df[self.TYPE] == type_sel) &
                np.isclose(self.df[self.DRAIN_V], float(vds_sel), atol=0.01)
        )

        # 筛选并处理数据
        filtered = self.df[mask][[self.GATE_V, self.DRAIN_I]].drop_duplicates().reset_index(drop=True)
        if not filtered.empty:
            return filtered[self.GATE_V].values, filtered[self.DRAIN_I].values
        else:
            return np.array([]), np.array([])  # 返回空数组避免解包错误

    def get_ws(self) -> list:
        """获取所有器件宽度值列表（升序排列）"""
        return self.df[self.W].drop_duplicates().sort_values().astype(float).tolist()

    def get_ls(self) -> list:
        """获取所有器件长度值列表（升序排列）"""
        return self.df[self.L].drop_duplicates().sort_values().astype(float).tolist()


    def set_cox_area(self, Cox_area: float):
        self.Cox_area = Cox_area
    # 使用transfer实验数据计算 μ_FE
    def u_fe_computer(self ,W, L):
        dv_dict = self.data_drain_tree[W][L]["1"]  # 注意 TO 类型是字符串
        vds_ls = list(dv_dict.keys())  # 将字典键转换为电压值列表

        # 添加类型检查
        if not vds_ls or len(vds_ls) < 2:
            raise ValueError("至少需要两个Vds数据点进行计算")

        # 确保电压值为浮点数
        x_1, y_1 = self.get_transfer_data(W, L, 1, float(vds_ls[0]))
        x_2, y_2 = self.get_transfer_data(W, L, 1, float(vds_ls[-1]))

        dI_DS_dV_GS_1 = np.gradient(y_1, x_1)  # 一阶导数
        dI_DS_dV_GS_2 = np.gradient(y_2, x_2)  # 一阶导数
        d2I_DS_dV_GS2 = np.gradient(dI_DS_dV_GS_2, x_1)  # 二阶导数
        max_idx = np.argmax(d2I_DS_dV_GS2)  # 找到最大值的索引（对应的是阈值电压点）
        V_th = x_2[max_idx]
        U_FE_1 = dI_DS_dV_GS_1 * (L / (W * self.Cox_area * vds_ls[0]))  # 使用线性区公式计算出的 μ_FE
        #
        mask = (x_2 - V_th) > 0.001  # 布尔数组，True 对应满足条件的点
        U_FE_2 = np.full_like(x_1, np.nan)  # 初始化全为 NaN
        U_FE_2[mask] = dI_DS_dV_GS_2[mask] * (L / (W * self.Cox_area * (x_1[mask] - V_th)))  # 饱和区公式计算的 μ_FE
        #
        log_IDS = np.log10(np.abs(y_1))
        SS = np.gradient(x_1, log_IDS)
        #
        return U_FE_1, U_FE_2, SS, V_th


    def get_vgs(self, w:float,l:float):
        """
        获取栅极电压值列表
        :param w: 器件宽度
        :param l: 器件长度
        :return: 栅极电压值列表
        """
        mask = (
                (self.df[self.W] == w) &
                (self.df[self.L] == l) &(self.df[self.TYPE] == 0)
        )

        # 筛选并处理数据
        filtered = self.df[mask][self.GATE_V].drop_duplicates().sort_values().reset_index(drop=True)

        # 返回栅压值列表（浮点型）
        return filtered.astype(float).tolist()

    # 传过来excel表内容和得到的W、L等可取值
    def get_Rc(self, ws:list, ls:list, vgs_ls:list, data_params,enable_rc=True,max_it = 100,error_tor = 0.01):
        # global Vc
        # global coeffs
        # coeffs = None
        # 初始化数组，维度为：[W][L][Vgs_num][4]，初值全为0

        print("计算接触电阻...")
        Rc_V = [[[[0 for _ in range(4)] for _ in range(len(vgs_ls))] for _ in range(len(ls))] for _ in range(len(ws))]
        I_exp = [0] * 8
        I_text = [0 for _ in range(8)]
        for i in range(len(ws)):
            for j in range(len(ls)):
                for k in range(len(vgs_ls)):
                    x, y = self.get_output_data(ws[i], ls[j], 0, vgs_ls[k])
                    Vd_arry = self.get_four_point(x)
                    Rc_V[i][j][k] = [Vd_arry[0] / 2, Vd_arry[1] / 2, Vd_arry[2] / 2, Vd_arry[3] / 2, Vd_arry[4] / 2,
                                     Vd_arry[5] / 2, Vd_arry[6] / 2, Vd_arry[7] / 2]
                    for text_num in range(8):  # 循环处理四个点(0-3)
                        for ii in range(len(x)):
                            if abs(x[ii] - Vd_arry[text_num]) < 0.01:
                                I_exp[text_num] = y[ii]
                        self.Vc = Rc_V[i][j][k][text_num]
                        I_text[text_num] = self.TCAD_I_simulation(0, vgs_ls[k], Vd_arry[text_num], data_params, ws[i], ls[j],
                                                             vgs_ls)
                        left = 0
                        right = Vd_arry[text_num]
                        iteration_count = 0
                        max_iterations = max_it  # 防止无限循环的最大迭代次数
                        while (abs(I_exp[text_num] - I_text[text_num]) / I_exp[
                            text_num] > error_tor and iteration_count < max_iterations):
                            if (I_exp[text_num] > I_text[text_num]):
                                right = Rc_V[i][j][k][text_num]
                                Rc_V[i][j][k][text_num] = (Rc_V[i][j][k][text_num] + left) / 2
                            else:
                                left = Rc_V[i][j][k][text_num]
                                Rc_V[i][j][k][text_num] = (Rc_V[i][j][k][text_num] + right) / 2
                            self.Vc = Rc_V[i][j][k][text_num]
                            I_text[text_num] = self.TCAD_I_simulation(0, vgs_ls[k], Vd_arry[text_num], data_params, ws[i],
                                                                 ls[j], vgs_ls)
                            iteration_count += 1
        # if not enable_rc:
        #     Rc_V = np.zeros_like(Rc_V)
        #     Vd_arry = np.zeros_like(Vd_arry)
        #     pass
        return Rc_V, Vd_arry

    def get_output_data(self, w_sel: float, l_sel: float, type_sel: int, vgs_sel: float):
        """获取输出特性数据
        参数:
            w_sel: 器件宽度
            l_sel: 器件长度
            type_sel: 测试类型 (0/1)
            vgs_sel: 栅极电压值
        返回:
            (x, y) 元组，包含漏压和漏极电流数据
        """
        # 构建筛选条件
        mask = (
                (self.df[self.W] == w_sel) &
                (self.df[self.L] == l_sel) &
                (self.df[self.TYPE] == type_sel) &
                np.isclose(self.df[self.GATE_V], float(vgs_sel), atol=0.00001)
        )

        # 筛选并处理数据
        filtered = self.df[mask][[self.DRAIN_V, self.DRAIN_I]].drop_duplicates().reset_index(drop=True)

        if not filtered.empty:
            return filtered[self.DRAIN_V].values, filtered[self.DRAIN_I].values
        else:
            return np.array([]), np.array([])  # 返回空数组避免解包错误

    def get_four_point(self, arr, num_points=8):
        n = len(arr)
        if n < num_points:
            return arr  # 元素不足则直接返回全部
        step = (n - 1) / (num_points - 1)
        return [arr[round(i * step)] for i in range(num_points)]

    def TCAD_I_simulation(self,type_sel, Vbias, Vswp, data_params, W, L, V_sl):
        # L = 50
        r_inner = 2 * math.pi * W
        # r_inner = 247  # nm
        # 设置实例变量以便在辅助函数中使用
        self.Ntail_eff = data_params['N_tail'] / 1e18
        self.Ndeep_eff = data_params['N_deep'] / 1e18
        # 解析新的参数并设置对应的值
        self.ufree = data_params['mu_free']
        self.Vfb = data_params['Vfb']
        self.phi_F0 = data_params['phi_F0']
        # 使用局部变量传递给计算函数
        phi_tail = data_params['phi_tail']
        phi_deep = data_params['phi_deep']

        # 处理Vswp为单个数字的情况
        if np.isscalar(Vswp):
            Vswp = np.array([Vswp])  # 转换为单元素数组
        Ids = np.zeros_like(Vswp)  # 初始化电流数组


        if type_sel == 0:
            myVy = Vswp
            Vg = Vbias
            V_sl = [float(x) for x in V_sl]
            for i, Vy in enumerate(myVy):
                if Vg in V_sl and self.coeffs_list:
                    index = V_sl.index(Vg)
                    self.Vc = self.predict_Vg_Rc(index, Vy)
                elif self.coeffs is not None:
                    self.Vc = self.predict_R(Vy, Vg)

                # self.Vc = 0.687672607
                if (Vy <= 0):
                    self.Vc = 0

                if (Vg < 0 and self.coeffs is not None):
                    self.Vc = self.predict_R(Vy, 0)
                phi_ss = (self.phi_s_free(0, Vg) ** self.n + self.phi_s_tail(0, Vg, phi_tail) ** self.n + self.phi_s_deep(0, Vg,
                                                                                                 phi_deep) ** self.n) ** (
                                     1 / self.n)
                phi_sd = (self.phi_s_free(Vy - self.Vc, Vg) ** self.n + self.phi_s_tail(Vy - self.Vc, Vg, phi_tail) ** self.n + self.phi_s_deep(Vy - self.Vc,
                                                                                                             Vg,
                                                                                                             phi_deep) ** self.n) ** (
                                     1 / self.n)
                Ids0 = (self.Ids_free(self.Vc, Vy, Vg, L, r_inner) ** self.m + self.Ids_tail(self.Vc, Vy, Vg, phi_tail, L,
                                                                         r_inner) ** self.m + self.Ids_deep(self.Vc, Vy, Vg, phi_deep,
                                                                                                  L, r_inner) ** self.m) ** (
                                   1 / self.m)
                Ids[i] = (1 + self.M * (Vy - (phi_sd - phi_ss))) * Ids0
        else:
            myVg = Vswp
            Vy = Vbias
            for i, Vg in enumerate(myVg):
                if hasattr(self, 'coeffs') and self.coeffs is not None:
                    self.Vc = self.predict_R(Vy, Vg)
                else:
                    self.Vc = 0
                if (Vy <= 0):
                    self.Vc = 0

                if(Vg<0 and self.coeffs is not None):
                    self.Vc = self.predict_R(Vy, 0)

                phi_ss = (self.phi_s_free(0, Vg) ** self.n + self.phi_s_tail(0, Vg, phi_tail) ** self.n + self.phi_s_deep(0, Vg,
                                                                                                 phi_deep) ** self.n) ** (
                                     1 / self.n)
                phi_sd = (self.phi_s_free(Vy, Vg) ** self.n + self.phi_s_tail(Vy, Vg, phi_tail) ** self.n + self.phi_s_deep(Vy, Vg,
                                                                                                   phi_deep) ** self.n) ** (
                                     1 / self.n)
                Ids0 = (self.Ids_free(self.Vc, Vy, Vg, L, r_inner) ** self.m + self.Ids_tail(self.Vc, Vy, Vg, phi_tail, L,
                                                                         r_inner) ** self.m + self.Ids_deep(self.Vc, Vy, Vg, phi_deep,
                                                                                                  L, r_inner) ** self.m) ** (
                                   1 / self.m)
                Ids[i] = (1 + self.M * (Vy - (phi_sd - phi_ss))) * Ids0

        if np.isscalar(Vswp) and len(Ids) == 1:
            return Ids[0]
        return Ids

    def predict_R(self, Vd, Vg):

        terms = [Vd ** i * Vg ** j for i in range(5) for j in range(5) if i + j <= 4]
        a = sum(c * t for c, t in zip(self.coeffs, terms))
        return a

    def predict_Vg_Rc(self, Vg_index, Vd):
        coeff = self.coeffs_list[Vg_index]  # 获取对应Vg的拟合系数
        # Rc = coeff[0] * Vd**2 + coeff[1] * Vd + coeff[2]
        Rc = coeff[0] * Vd ** 3 + coeff[1] * Vd ** 2 + coeff[2] * Vd + coeff[3]
        return Rc

    def fit_poly3_2d(self,R, Vg_list, Vd_list):

        R = np.array(R).T
        Vg_list = np.array(Vg_list, dtype=float)
        Vd_list = np.array(Vd_list, dtype=float)
        Vd_grid, Vg_grid = np.meshgrid(Vd_list, Vg_list, indexing='ij')
        X = Vd_grid.ravel()
        Y = Vg_grid.ravel()
        Z = R.ravel()
        A = np.column_stack([X ** i * Y ** j for i in range(5) for j in range(5) if i + j <= 4])
        self.coeffs, _, _, _ = np.linalg.lstsq(A, Z, rcond=None)


    # region  原来的计算函数
    def phi_s_free(self,Vy, Vg):
        mp = (self.q_element / self.eps_s) * self.Nfree * (1E18) * (1E6)
        Ap = np.exp(-(self.phi_F0 + Vy) / (2 * self.VT)) * (self.eps_s / self.Cox_area) * (mp / (2 * self.VT)) ** 0.5
        phi_surface = (Vg -self. Vfb) - 2 * (self.VT) * lambertw(Ap * np.exp(0.5 * (Vg - self.Vfb) / self.VT))
        return np.real(phi_surface)

    '解析free电流'
    '类似的把电流也写成一个函数'

    def Ids_free(self,Vc, Vy, Vg, L, r_inner):  # 处理的是漏端含有Vc
        # phi_eff = 0.0245 - (0.0245-0.022) * (1 / (1 + np.exp(-10 * (Vy - 0.5))))
        phi_ss = self.phi_s_free(0, Vg)
        phi_sd = self.phi_s_free(Vy - Vc, Vg)
        phi_ss_ref = phi_ss
        phi_sd_ref = phi_sd
        D = (1 / self.VT) - 1 / (2 * self.VT)
        Nfree_ref = self.Nfree * (1E24)
        C_star = (1 / D) * self.Nfree * (1E24) * math.sqrt(self.q_element * self.eps_s) * (1 / math.sqrt(2 * Nfree_ref * self.VT)) * \
                 ((2 * self.q_element * self.eps_s * Nfree_ref * self.VT) ** (-self.VT * D))
        Ids = 2 * np.pi * (r_inner / L) * (1E-4) * self.ufree * C_star * (self.Cox_area ** (2 * D * self.VT)) * (
                ((Vg - self.Vfb - phi_ss_ref) ** (2 * D * self.VT + 1) - (Vg - self.Vfb - phi_sd_ref) ** (2 * D * self.VT + 1)) / (
                    2 * D * self.VT + 1)
                + self.VT * ((Vg - self.Vfb - phi_ss_ref) ** (2 * D * self.VT) - (Vg - self.Vfb - phi_sd_ref) ** (2 * D * self.VT))
        )
        return Ids * (1 + self.DIBL_A * Vy **self. DIBL_B)

    def phi_s_tail(self,Vy, Vg, phi_tail):
        delta_n = 1
        mp = (self.q_element / self.eps_s) * self.Ntail_eff * (1E18) * (1E6)
        Ap = np.exp(-(self.phi_F0 + Vy) / (2 * phi_tail)) * (self.eps_s / self.Cox_area) * (mp / (2 * phi_tail)) ** 0.5
        phi_surface = (Vg - self.Vfb) - 2 * phi_tail * lambertw(Ap * np.exp((Vg - self.Vfb) / 2 / phi_tail))
        return np.real(phi_surface)

    '解析tail电流'
    '类似的把电流也写成一个函数'

    def Ids_tail(self,Vc, Vy, Vg, phi_tail, L, r_inner):
        phi_ss = self.phi_s_tail(0, Vg, phi_tail)
        phi_sd = self.phi_s_tail(Vy - Vc, Vg, phi_tail)
        phi_ss_ref = phi_ss + (phi_sd - phi_ss) * self.resis
        phi_sd_ref = phi_sd - (phi_sd - phi_ss) *self. resis
        D = 1 / self.VT - 1 / (2 * phi_tail)  # 1/V
        Ntail_ref = self.Ntail_eff * (1E24)  # 1/m3
        C_star = (1 / D) * self.Nfree * (1E24) * math.sqrt(self.q_element * self.eps_s) * (1 / math.sqrt(2 * Ntail_ref * phi_tail)) * \
                 ((2 * self.q_element * self.eps_s * Ntail_ref * phi_tail) ** (-phi_tail * D))

        Ids = 2 * np.pi * (r_inner / L) * (1E-4) * self.ufree * C_star * (self.Cox_area ** (2 * D * phi_tail)) * (
                ((Vg - self.Vfb - phi_ss_ref) ** (2 * D * phi_tail + 1) - (Vg - self.Vfb - phi_sd_ref) ** (
                            2 * D * phi_tail + 1)) / (2 * D * phi_tail + 1)
                + self.VT * ((Vg - self.Vfb - phi_ss_ref) ** (2 * D * phi_tail) - (Vg - self.Vfb - phi_sd_ref) ** (2 * D * phi_tail))
        )
        return Ids * (1 + self.DIBL_A * Vy ** self.DIBL_B)

    def phi_s_deep(self,Vy, Vg, phi_deep):
        delta_n = 1
        mp = (self.q_element / self.eps_s) * self.Ndeep_eff * (1E18) * (1E6)
        Ap = np.exp(-(self.phi_F0 + Vy) / (2 * phi_deep)) * (self.eps_s / self.Cox_area) * (mp / (2 * phi_deep)) ** 0.5
        phi_surface = (Vg - self.Vfb) - 2 * phi_deep * lambertw(Ap * np.exp((Vg - self.Vfb) / 2 / phi_deep))
        return np.real(phi_surface)

    '解析tail电流'
    '类似的把电流也写成一个函数'

    def Ids_deep(self,Vc, Vy, Vg, phi_deep, L, r_inner):
        phi_ss = self.phi_s_deep(0, Vg, phi_deep)
        phi_sd = self.phi_s_deep(Vy - Vc, Vg, phi_deep)
        phi_ss_ref = phi_ss + (phi_sd - phi_ss) * self.resis
        phi_sd_ref = phi_sd - (phi_sd - phi_ss) * self.resis
        D = 1 / self.VT - 1 / (2 * phi_deep)
        Ndeep_ref = self.Ndeep_eff * (1E24)
        C_star = (1 / D) * self.Nfree * (1E24) * math.sqrt(self.q_element * self.eps_s) * (1 / math.sqrt(2 * Ndeep_ref * phi_deep)) * \
                 ((2 * self.q_element * self.eps_s * Ndeep_ref * phi_deep) ** (-phi_deep * D))

        Ids = 2 * np.pi * (r_inner / L) * (1E-4) * self.ufree * C_star * (self.Cox_area ** (2 * D * phi_deep)) * (
                ((Vg - self.Vfb - phi_ss_ref) ** (2 * D * phi_deep + 1) - (Vg - self.Vfb - phi_sd_ref) ** (
                            2 * D * phi_deep + 1)) / (2 * D * phi_deep + 1)
                + self.VT * ((Vg - self.Vfb - phi_ss_ref) ** (2 * D * phi_deep) - (Vg - self.Vfb - phi_sd_ref) ** (2 * D * phi_deep))
        )
        return Ids * (1 + self.DIBL_A * Vy ** self.DIBL_B)
    # endregion


