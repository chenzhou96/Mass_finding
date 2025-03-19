import os
import logging
import datetime
import csv
import json
from pathlib import Path
from ..config.base_config import BaseConfig
from ..config.path_config import PathManager

# ----------------------------   导出器工厂   ----------------------------
class CSVExporter_formulaGeneration:
    def export(self, results: dict):
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path_manager = PathManager()
            path_manager.get_mass_finding_cache_path()
            csv_path = os.path.join(path_manager.get_formula_generation_cache_path(), f'mass_data_{timestamp}.csv')

            # 修改编码为 utf-8-sig 解决中文乱码
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 参数信息部分保持不变
                input_params = results["input_params"]
                writer.writerow([
                    f"ms_mode: {input_params['ms_mode']}",
                    f"adduct_model: {', '.join(input_params['adduct_model'])}",
                    f"m/z: {input_params['m2z']}",
                    f"error: {input_params['error_pct']}%",
                    f"charge: {input_params['charge']}",
                    f"elements: {input_params['elements']}",
                    
                ])
                
                # 更新表头添加 molecular_weight
                writer.writerow([
                    'C', 'H', 'O', 'N', 'S', 'P', 'Si', 'B', 'Se',
                    'F', 'Cl', 'Br', 'I', 'ion', 'dbr', 
                    'predicted_mz', 'molecular_weight'  # 新增列
                ])

                # 更新数据行添加分子量
                for adduct, formulas in results["formulas"].items():
                    for formula in formulas:
                        writer.writerow([
                            formula['elements'].get('C', 0),
                            formula['elements'].get('H', 0),
                            formula['elements'].get('O', 0), 
                            formula['elements'].get('N', 0),
                            formula['elements'].get('S', 0),
                            formula['elements'].get('P', 0),
                            formula['elements'].get('Si', 0),
                            formula['elements'].get('B', 0),
                            formula['elements'].get('Se', 0),
                            formula['elements'].get('F', 0),
                            formula['elements'].get('Cl', 0),
                            formula['elements'].get('Br', 0),
                            formula['elements'].get('I', 0),
                            adduct,
                            f"{formula['dbr']:.1f}",
                            f"{formula['mz']:.4f}",
                            f"{formula['predicted_mw']:.4f}"  # 新增分子量数据
                        ])

            logging.info(f"CSV 文件已成功导出: {csv_path}")
        except Exception as e:
            logging.error(f"CSV 导出失败: {e}")
            raise

class JSONExporter_formulaGeneration:
    def export(self, results: dict):
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path_manager = PathManager()
            path_manager.get_mass_finding_cache_path()
            json_path = os.path.join(path_manager.get_formula_generation_cache_path(), f'mass_data_{timestamp}.json')

            # 构建完整数据结构
            data_to_save = {
                "metadata": {
                    "export_time": datetime.datetime.now().isoformat(),
                    "software_version": BaseConfig.VERSION,
                },
                "input_params": results["input_params"],  # 使用完整输入参数
                "results": []
            }

            # 重组结果数据
            for adduct_type, formulas in results["formulas"].items():
                for formula in formulas:
                    data_to_save["results"].append({
                        "formula": formula['elements'],
                        "adduct_type": adduct_type,
                        "calculated_properties": {
                            "dbr": formula['dbr'],
                            "predicted_mz": formula['mz'],
                            "molecular_weight": formula['predicted_mw']
                        }
                    })

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)

            logging.info(f"JSON 文件已成功导出: {json_path}")

            return data_to_save
        
        except Exception as e:
            logging.error(f"JSON 导出失败: {e}", exc_info=True)
            raise

class JSONExporter_formulaSearch_PubChem:
    def export(self, results: tuple):
        # 传递的参数是元组，形式（molecular_formula: str, compounds: list）
        try:
            molecular_formula, compounds = results
            results_list = []
            count = 0

            if compounds:
                first_compound = compounds[0]
                monoisotopic_mass = first_compound.monoisotopic_mass
                molecular_weight = first_compound.molecular_weight
            else:
                monoisotopic_mass = None
                molecular_weight = None

            for compound in compounds:
                data = {
                    "iupac_name": compound.iupac_name,
                    "cid": compound.cid,
                    "isomeric_smiles": compound.isomeric_smiles,
                    "canonical_smiles": compound.canonical_smiles,
                }
                results_list.append(data)
                count += 1

            # 构建完整数据结构
            data_to_save = {
                "metadata": {
                    "export_time": datetime.datetime.now().isoformat(),
                    "software_version": BaseConfig.VERSION,
                    "molecular_formula": molecular_formula,
                    "result_count": count,
                    "monoisotopic_mass": monoisotopic_mass,
                    "molecular_weight": molecular_weight
                },
                "results": results_list
            }

            output_filename = f"formula_search_results_{molecular_formula}.json"
            path_manager = PathManager()
            path_manager.get_mass_finding_cache_path()
            output_path = path_manager.get_formula_search_cache_path / output_filename

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)

            logging.info(f"结果已保存到 {output_path}")
            logging.info(f"化学式 {molecular_formula} 检索到 {count} 条信息")

            return data_to_save

        except Exception as e:
            logging.error(f"JSON 导出失败: {e}")
            raise

class ExporterFactory:
    @staticmethod
    def get_exporter(format_type):
        exporters = {
            'csv_formulaGeneration': CSVExporter_formulaGeneration(),
            'json_formulaGeneration': JSONExporter_formulaGeneration(),
            'json_formulaSearch_PubChem': JSONExporter_formulaSearch_PubChem(),

        }
        return exporters.get(format_type, None)

# --------------------------   配置文件管理器   --------------------------
class ChemElementConfigValidator:
    @staticmethod
    def validate_keys(config, required_keys):
        if not all(k in config for k in required_keys):
            raise ValueError("Invalid config format: 缺少必要的配置项")

    @staticmethod
    def validate_atomic_weights(atomic_weights):
        if not isinstance(atomic_weights, dict) or not all(isinstance(v, (int, float)) for v in atomic_weights.values()):
            raise ValueError("Invalid atomic_weights format")

    @staticmethod
    def validate_adducts(adducts, ion_weights):
        if not isinstance(adducts, dict):
            raise ValueError("Invalid adducts format")
        for mode, adduct_dict in adducts.items():
            if not isinstance(adduct_dict, dict) or not all(ion in ion_weights for ion in adduct_dict.values()):
                raise ValueError(f"Invalid adducts format for mode {mode}")

class ReadChemElementConfig:
    def __init__(self, config_path: Path):
        self.config = self.load_config(config_path)
        self.validate_config()

    def load_config(self, config_path: Path):
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")
        with config_path.open('r', encoding='utf-8') as f:
            return json.load(f)

    def validate_config(self):
        ChemElementConfigValidator.validate_keys(self.config, {'atomic_weights', 'ion_weights', 'adducts', 'element_categories'})
        ChemElementConfigValidator.validate_atomic_weights(self.config['atomic_weights'])
        ChemElementConfigValidator.validate_adducts(self.config['adducts'], self.config['ion_weights'])

# 示例调用
if __name__ == "__main__":
    pass