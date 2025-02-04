import time
import csv

# ******************** 配置参数 ********************
# 可选 'ESI+' or 'ESI-' or 'EI+' or 'EI-'
MS_MODE = 'ESI+'
# 质荷比
M2Z = 100.0000
# 误差范围 (%)
ERROR_PERCENT = 0.1
# 电荷数
CHARGE = 1
# ******************** 参数结束 ********************

# 原子量数据 (精确质量)
ATOMIC_WEIGHTS = {
    'H': 1.007825, 'C': 12.000000, 'N': 14.003074, 'O': 15.994915,
    'F': 18.998403, 'Si': 27.976927, 'P': 30.973762, 'B': 11.009305,
    'S': 31.972071, 'Cl': 34.968853, 'Br': 78.918338, 'Se': 79.916521,
    'I': 126.904473, 
}

ION_WEIGHTS = {
    'e+': 0.0000, 'e-': 0.0000, 
    'Na+': 22.989769, 'K+': 38.963707, 'H3O+': 19.01839, 'NH4+': 18.034374,
    'H+': 1.007825, 'H-': -1.007825, 'Cl-': 34.968853, 'HCOO-': 44.997655,
    'CH3COO-': 59.013305, 
}

# 加合离子配置
ADDUCTS = {
    'ESI+': {
        'H+': ION_WEIGHTS['H+'],
        'H3O+': ION_WEIGHTS['H3O+'],
        'NH4+': ION_WEIGHTS['NH4+'],
        'Na+': ION_WEIGHTS['Na+'],
        'K+': ION_WEIGHTS['K+']
    },
    'ESI-': {
        'H-': ION_WEIGHTS['H-'],
        'Cl-': ION_WEIGHTS['Cl-'],
        'HCOO-': ION_WEIGHTS['HCOO-'],
        'CH3COO-': ION_WEIGHTS['CH3COO-'],
    },
    'EI+': {
        'e+': ION_WEIGHTS['e+'],
    },
    'EI-': {
        'e-': ION_WEIGHTS['e-'],
    },
}

class ChemFormula():
    def __init__(self) -> None:
        """储存分子式"""

        self.elements = {
            'H': 0, 'F': 0, 'Cl': 0, 'Br': 0, 'I': 0,
            'B': 0, 'N': 0, 'P': 0, 
            'C': 0, 'Si': 0,
            'O': 0, 'S': 0, 'Se': 0,
        }

        self.Valency_1 = 0
        self.Valency_3 = 0
        self.Valency_4 = 0

        self.even = False
        self.dbr = 0
        self.p_mw = 0

    def verify_valency(self) -> bool:
        """
        校验分子式是否满足化合价规律 不饱和度是否大于等于零
        """

        self.Valency_1 = self.elements['H'] + self.elements['F'] + self.elements['Cl'] + self.elements['Br'] + self.elements['I']
        self.Valency_3 = self.elements['B'] + self.elements['N'] + self.elements['P']
        self.Valency_4 = self.elements['C'] + self.elements['Si']

        self.dbr = (2 * self.Valency_4 + 2 + self.Valency_3 - self.Valency_1) / 2

        if self.dbr < 0:
            return False

        self.even = (((self.dbr * 2) % 2) == 0)
        
        return self.even
    
    def predict_mw(self) -> float:
        """"""

        for element, number in self.elements.items():
            self.p_mw += ATOMIC_WEIGHTS[element] * number

        return self.p_mw

def calculate_molecular_weight(ms_mode, m2z, charge) -> dict:
    '''根据质谱模式和质谱峰计算可能分子量'''

    mw_dict = dict()

    for mode, ion in ADDUCTS[ms_mode].items():
        mw_dict[mode] = m2z * charge - ion * charge

    return mw_dict

def find_chem_formula(mw: float, error: float) -> list:
    '''根据目标分子量和误差范围，找出所有满足条件的化学式组合'''
    
    mw_error = mw * error
    mw_min = mw - mw_error
    mw_max = mw + mw_error

    # 按原子量降序排列的元素列表（不包含氢）
    elements = [
        ('I', ATOMIC_WEIGHTS['I']),
        ('Br', ATOMIC_WEIGHTS['Br']),
        ('Se', ATOMIC_WEIGHTS['Se']),
        ('S', ATOMIC_WEIGHTS['S']),
        ('Cl', ATOMIC_WEIGHTS['Cl']),
        ('P', ATOMIC_WEIGHTS['P']),
        ('Si', ATOMIC_WEIGHTS['Si']),
        ('F', ATOMIC_WEIGHTS['F']),
        ('O', ATOMIC_WEIGHTS['O']),
        ('N', ATOMIC_WEIGHTS['N']),
        ('C', ATOMIC_WEIGHTS['C']),
        ('B', ATOMIC_WEIGHTS['B']),
    ]
    H_weight = ATOMIC_WEIGHTS['H']

    chem_list = []

    def backtrack(index, remaining_mw, element_counts):
        """递归回溯函数处理元素组合"""
        if index == len(elements):
            # 处理氢原子数目
            H_num = round(remaining_mw / H_weight)
            # 创建化学式对象
            chem = ChemFormula()
            for (elem_name, _), count in zip(elements, element_counts):
                chem.elements[elem_name] = count
            chem.elements['H'] = H_num
            
            # 验证化合价和分子量范围
            if chem.verify_valency():
                predict_mw = chem.predict_mw()
                if mw_min < predict_mw < mw_max:
                    chem_list.append(chem)
            return

        # 当前处理元素信息
        elem_name, elem_weight = elements[index]
        max_num = int(remaining_mw / elem_weight)
        
        # 尝试所有可能的原子数量（从大到小尝试以加速剪枝）
        for num in range(max_num, -1, -1):
            new_remaining = remaining_mw - num * elem_weight
            current_sum = mw - new_remaining  # 已选元素的总分子量
            
            # 剪枝条件判断
            if current_sum > mw_max:
                continue  # 当前总和已超过最大值
            if current_sum + new_remaining < mw_min:
                continue  # 剩余部分全部用完也无法达到最小值
            
            # 进入下一层决策
            backtrack(index + 1, new_remaining, element_counts + [num])

    # 从第一个元素开始递归处理
    backtrack(0, mw, [])

    return chem_list

def data_analysis(ms_mode, m2z, error, charge) -> dict:
    """"""

    data = calculate_molecular_weight(ms_mode=ms_mode, m2z=m2z, charge=charge)

    results = dict()
    if data:
        for mode, mw in data.items():
            results[mode] = find_chem_formula(mw=mw, error=error)
        return results
    else:
        print('MS_MODE参数错误!!!')
        exit()

def main(ms_mode, m2z, error, charge):
    """"""

    start_time = time.time()
    i = 0

    data = data_analysis(ms_mode, m2z, error, charge)
    
    if data:
        with open(f'ms_data_{int(time.time())}.csv', 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([f'ms_mode: {ms_mode}', f'm/z: {m2z}', f'error: {error}', f'z: {charge}'])
            writer.writerow(['C', 'H', 'O', 'N', 'S', 'P', 'Si', 'B', 'Se', 'F', 'Cl', 'Br', 'I', 'ion', 'dbr', 'p_mw'])
            for key, values in data.items():
                for item in values:
                    i += 1
                    mw_ion = item.p_mw + charge * ADDUCTS[ms_mode][key]
                    writer.writerow([item.elements['C'],
                                     item.elements['H'],
                                     item.elements['O'],
                                     item.elements['N'],
                                     item.elements['S'],
                                     item.elements['P'],
                                     item.elements['Si'],
                                     item.elements['B'],
                                     item.elements['Se'],
                                     item.elements['F'],
                                     item.elements['Cl'],
                                     item.elements['Br'],
                                     item.elements['I'],
                                     key,
                                     item.dbr,
                                     format(mw_ion, '.4f'),
                                    ])
        print(f"生成完成！耗时 {time.time()-start_time:.2f} 秒")
        print(f"共找到 {i} 个可能分子式")

    else:
        print('没有找到可能分子式!!!')
        exit()

if __name__ == '__main__':
    
    # print('C\tSi\tB\tN\tP\tO\tS\tSe\tF\tCl\tBr\tI\tH\tdbr\tp_mw')
    # for item in find_chem_formula(100.00, 0.001):
    #     print(f'{item.C_num}\t{item.Si_num}\t{item.B_num}\t{item.N_num}\t{item.P_num}\t{item.O_num}\t{item.S_num}\t{item.Se_num}\t{item.F_num}\t{item.Cl_num}\t{item.Br_num}\t{item.I_num}\t{item.H_num}\t{item.dbr}\t{item.p_mw}')

    main(ms_mode=MS_MODE, m2z=M2Z, error=ERROR_PERCENT, charge=CHARGE)