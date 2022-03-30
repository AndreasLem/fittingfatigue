import pandas as pd
import numpy as np
import os
from pathlib import Path
from util_functions import *  # split_word_to_list, intersect_of_2_lists, dataframe_filter_only_above_nas


def main():
    path = r"C:\Users\AndreasLem\OneDrive - Groundline\Projects\NZ-6500 - Clevis fatigue load evaluations"
    input_file = "ClevisFatigue_Input.xlsx"
    results_file = "raft_moments_test.xlsx"
    df_loads = TowerLoads.read_attachment_loads(path, input_file, results_file)


class TowerLoads:
    def __init__(self, path, file_name, results_file):
        self.path_input = path
        self.file_name = file_name
        self.results_file_name = results_file
        'Dictionary to convert from naming in Excel sheet to format consistent with python code'
        self.convert_names_pls = {
            'Row #': 'row',
            'Str. No.': 'structure_number',
            'Str. Name': 'structure_name',
            'LC #': 'lc',
            'WC #': 'wc',
            'Load Case Description': 'lc_description',
            'Set No.': 'set_no',
            'Phase No.': 'phase_no',
            'Attach. Joint Labels': 'joint',
            'Structure Loads Vert. (N)': 'vertical',
            'Structure Loads Trans. (N)': 'transversal',
            'Structure Loads Long. (N)': 'longitudinal',
            'Loads from back span Vert. (N)': 'vertical_back',
            'Loads from back span Trans. (N)': 'transversal_back',
            'Loads from back span Long. (N)': 'longitudinal_back',
            'Loads from ahead span Vert. (N)': 'vertical_ahead',
            'Loads from ahead span Trans. (N)': 'transversal_ahead',
            'Loads from ahead span Long. (N)': 'longitudinal_ahead',
            'Warnings': 'warnings'
        }
        self.convert_names_general = {
            'Height [mm]:': 'height',
            'Width [mm]:': 'width',
            'Outer diameter [mm]:': 'd_outer',
            'Inner diameter [mm]:': 'd_inner',
            'Pin diameter [mm]:': 'd_pin',
            'Stem diameter [mm]:': 'd_stem',
            'Friction coefficient [-]:': 'friction',
            'Force arm distance [mm]:': 'force_arm',
            'Unit:': 'unit',
            'Line name:': 'line_id',
            'File name:': 'file_name'
        }
        self.unit_conversion = {
            'mm': 0.001,
            'cm': 0.01,
            'm': 1.,
            'mm2': 1.e-6,
            'cm2': 1.e-4,
            'm2': 1.
        }
        columns_keep = list(self.convert_names_pls.values())[:-7]
        self.convert_names_pls = {x: y for x, y in self.convert_names_pls.items() if y in columns_keep}
        self.convert_names_pls_back = {y: x for x, y in self.convert_names_pls.items()}
        'Setup for Excel and csv input'
        self.excel_object = self._init_excel_object()
        self.csv_objects = self._init_csv_objects()
        'Input variables'
        self.swivel_info = {}
        self.clevis_info = {}
        self.general_info = {}
        self.line_file_name_info = {}

    @classmethod
    def read_attachment_loads(cls, path, input_file, results_file):
        cls_obj = cls(path, input_file, results_file)
        'Get input for necessary for friction calculations'
        cls_obj.swivel_info = cls_obj._get_friction_info("GeneralInput", 1, ["Parameter", "Value"])
        cls_obj.clevis_info = cls_obj._get_friction_info("GeneralInput", 9, ["Parameter", "Value"])
        cls_obj.general_info = cls_obj._get_friction_info("GeneralInput", 14, ["Parameter", "Value"])
        cls_obj.general_info = cls_obj._get_friction_info("GeneralInput", 14, ["Parameter", "Value"])
        cls_obj.line_file_name_info = cls_obj._get_friction_info("FileInput", 0, ["Line name:", "File name:"])
        cls_obj.line_file_name_info = {y: x for x, y in cls_obj.line_file_name_info.items()}
        'Read loads from csv files'
        df = cls_obj._dataframe_setup()
        my = cls_obj.general_info["friction"]
        r_out = cls_obj.swivel_info["d_outer"] * cls_obj.unit_conversion[cls_obj.general_info["unit"]]
        r_in = cls_obj.swivel_info["d_inner"] * cls_obj.unit_conversion[cls_obj.general_info["unit"]]
        df["t1"] = df.apply(lambda x: friction_torsion_resistance_t1(my, x["transversal"], r_out, r_in), axis=1)

        return df

    def _get_friction_info(self, sheet, header_row, header_columns):
        '''
        Function to read swivel, clevis or friction info, as specified in Excel sheet, and store in self

        :param str sheet: Sheet name which data shall be extracted from
        :param int header_row: Index to specify header row of Dataframe
        :param list header_columns: Columns specifying header column of Dataframe

        :return: Information for friction calculations
        :rtype: dict
        '''
        df = self.excel_object.parse(
            index_col=None,
            skiprows=header_row,
            sheet_name=sheet,
            usecols=header_columns
        )
        df = dataframe_filter_only_above_nas(df, header_columns[1])
        df.loc[:, header_columns[0]] = df.loc[:, header_columns[0]].map(
            lambda x: self.convert_names_general[x] if x in self.convert_names_general else x
        )
        df = df.set_index([header_columns[0]])
        return df.to_dict()[header_columns[1]]

    @classmethod
    def get_maximum_lc_moments(cls, path, file_name, results_file):
        cls_obj = cls(path, file_name, results_file)
        # cls_obj._get_foundation_distance("JointSupportReactions", 1, 5)
        cls_obj._get_foundation_distance("VerificationLoads", 1, 5)
        cls_obj._get_foundation_moment_arms()
        # df = cls_obj._find_most_loaded_lcs_for_raft_foundations("JointSupportReactions", 7)
        df = cls_obj._find_most_loaded_lcs_for_raft_foundations("VerificationLoads", 7)
        cls_obj._write_foundation_forces_to_excel(df)

    def _dataframe_setup(self):
        line_list = []
        for file_name in self.csv_objects:
            df = pd.read_csv(os.path.join(self.path_input, file_name))
            df.columns = df.columns.map(lambda x: self.convert_names_pls[x] if x in self.convert_names_pls else x)
            df = df.loc[:, list(self.convert_names_pls.values())]
            line_id = Path(file_name).stem.split()[0]
            df["line_id"] = self.line_file_name_info[file_name]
            'Add dataframe to existing'
            if "df_total" in locals():
                df_total = pd.concat([df_total, df])
            else:
                df_total = df

        return df_total

    def _init_excel_object(self):
        '''
        Open Excel object for read

        :return All Excel sheets stored in object for data extraction
        :rtype pandas.ExcelFile ExcelObj
        '''
        ExcelObj = pd.ExcelFile(os.path.join(self.path_input, self.file_name))
        return ExcelObj

    def _init_csv_objects(self):
        """
        Function to return all 'csv' files in folder

        :return: 'csv' files to be evaluated
        :rtype: list
        """
        file_names = os.listdir(self.path_input)
        return_names = []
        for file_name in file_names:
            if Path(file_name).suffix.strip(".") == "csv":
                return_names.append(file_name)
        return return_names

    def _write_foundation_forces_to_excel(self, df):
        '''Write to file for all towers'''
        file_name = os.path.join(self.path_input, self.results_file_name)
        counter, counter2 = 0, 0
        with pd.ExcelWriter(file_name) as writer:
            counter =+1
            for tow, res in df.groupby("structure_number"):
                counter2 += 1
                res = res.sort_values(by=["m_tot_res", "foundation"], ascending=False)
                res.columns = res.columns.map(lambda x: self.convert_names_pls_back[x] if x in self.convert_names_pls_back else x)
                res.to_excel(
                    writer,
                    sheet_name=str(tow)
                )

    def _get_foundation_moment_arms(self):
        arm = self.foundation_distance / 2.
        height = self.foundation_height
        self.pls_foundation_moment_arms = {
            1: [arm, -arm, height],
            2: [-arm, -arm, height],
            3: [-arm, arm, height],
            4: [arm, arm, height]
        }

    def _get_foundation_distance(self, sheet, header_row, header_column):
        '''
        Function to get foundation distance, as specified in Excel sheet, and store in self

        :param str sheet: Sheet name which data shall be extracted from
        :param int header_row: Index to specify header row of Dataframe
        :param int header_column: Index to specify header column of Dataframe

        '''
        inp_df = self.excel_object.parse(
            index_col=None,
            skiprows=header_row,
            sheet_name=sheet,
        )
        inp_df.columns = inp_df.columns.map(lambda x: self.convert_names_pls[x] if x in self.convert_names_pls else x)

        'Filter to store only relevant list values'
        na_indexes = list(np.flatnonzero(inp_df.iloc[:, header_column].isna()))  # Find NaN cells to define where lists end
        'Use first NaN cell to define end of list'
        inp_df = inp_df.iloc[0:na_indexes[0], :] if len(na_indexes) > 0 else inp_df
        self.foundation_distance = inp_df.loc[:, "foundation_dist"].iloc[0]
        self.foundation_height = inp_df.loc[:, "foundation_height"].iloc[0]

    def _find_most_loaded_lcs_for_raft_foundations(self, sheet, header_label_index):
        '''
        Function to convert moment and forces for each individual foundation chimney to total raft moment.

        :param str sheet: Sheet name which data shall be extracted from
        :param int header_label_index: Index to specify header row of Dataframe

        :return:
        :rtype:
        '''

        inp_df = self.excel_object.parse(
            index_col=None,
            skiprows=header_label_index,
            sheet_name=sheet,
        )
        'Filter to store only relevant list values'
        na_indexes = list(np.flatnonzero(inp_df.iloc[:, 1].isna()))  # Find NaN cells to define where lists end
        'Use first NaN cell to define end of list'
        inp_df = inp_df.iloc[0:na_indexes[0], :] if len(na_indexes) > 0 else inp_df
        'Change names to avoid special characters'

        inp_df.columns = inp_df.columns.map(lambda x: self.convert_names_pls[x] if x in self.convert_names_pls else x)
        inp_df = inp_df.applymap(lambda x: x.replace('"', '').replace("'", "").strip() if isinstance(x, str) else x)

        'Store data'
        result_dict = {}
        counter = 0
        for tower_type, tow_item in inp_df.groupby("structure_number"):
            for lc, lc_item in tow_item.groupby("lc"):
                if lc_item.shape[0] > 1:
                    lc_item["joint_check"] = lc_item.loc[:, "joint"].map(
                        lambda x: intersect_of_2_lists(
                            split_word_to_list(x.lower()),
                            self.pls_foundation_ids.keys()
                        )
                    )
                    lc_item["foundation"] = lc_item.loc[:, "joint_check"].map(
                        lambda x: self.pls_foundation_ids[x[0]] if len(x) > 0 else "foundation id not found"
                    )
                    lc_item = lc_item.set_index("foundation")
                    'Set up moment arms'
                    lc_item["arm_long"] = lc_item.index.map(
                        {x: y[0] for x, y in self.pls_foundation_moment_arms.items()}
                    )
                    lc_item["arm_tran"] = lc_item.index.map(
                        {x: y[1] for x, y in self.pls_foundation_moment_arms.items()}
                    )
                    lc_item["arm_vert"] = lc_item.index.map(
                        {x: y[2] for x, y in self.pls_foundation_moment_arms.items()}
                    )
                    'Calculate contributions to total bending moment about x, y, z axes'
                    lc_item["m_tot_long_part"] = lc_item.loc[:, "m_long"] + \
                                                 lc_item.loc[:, "f_vert"] * lc_item.loc[:, "arm_tran"] - \
                                                 lc_item.loc[:, "f_tran"] * lc_item.loc[:, "arm_vert"]
                    lc_item["m_tot_tran_part"] = lc_item.loc[:, "m_tran"] - \
                                                 lc_item.loc[:, "f_vert"] * lc_item.loc[:, "arm_long"] + \
                                                 lc_item.loc[:, "f_long"] * lc_item.loc[:, "arm_vert"]
                    lc_item["m_tot_vert_part"] = lc_item.loc[:, "m_vert"] - \
                                                 lc_item.loc[:, "f_long"] * lc_item.loc[:, "arm_tran"] + \
                                                 lc_item.loc[:, "f_tran"] * lc_item.loc[:, "arm_long"]
                    'Calculate total raft bending moments'
                    m_x, m_y, m_z = lc_item["m_tot_long_part"].sum(), lc_item["m_tot_tran_part"].sum(), lc_item["m_tot_vert_part"].sum()
                    lc_item["m_tot_long"] = m_x.round(2)
                    lc_item["m_tot_tran"] = m_y.round(2)
                    lc_item["m_tot_vert"] = m_z.round(2)
                    lc_item["m_tot_res"] = np.sqrt(m_x ** 2 + m_y ** 2).round(2)
                else:
                    lc_item["foundation"] = 1
                    lc_item = lc_item.set_index("foundation")
                    lc_item["m_tot_long_part"] = lc_item.loc[:, "m_long"]
                    lc_item["m_tot_tran_part"] = lc_item.loc[:, "m_tran"]
                    lc_item["m_tot_vert_part"] = lc_item.loc[:, "m_vert"]
                    lc_item["m_tot_long"] = lc_item.loc[:, "m_long"]
                    lc_item["m_tot_tran"] = lc_item.loc[:, "m_tran"]
                    lc_item["m_tot_vert"] = lc_item.loc[:, "m_vert"]
                    lc_item["m_tot_res"] = lc_item.loc[:, "m_res"]

                lc_item = lc_item.loc[:, [
                                             "row", "structure_number", "joint", "m_tot_long",  "m_tot_tran",
                                             "m_tot_vert", "m_tot_res", "m_long", "m_tran", "m_vert", "f_long",
                                             "f_tran", "f_vert", "lc", "structure_name"
                                         ]
                          ]
                for row, item in lc_item.iterrows():
                    result_dict[counter] = item.to_dict()
                    result_dict[counter].update({"structure_number": tower_type})
                    result_dict[counter].update({"lc": lc})
                    result_dict[counter].update({"foundation": row})
                    counter += 1

        df = pd.DataFrame(result_dict).transpose()

        return df


if __name__ == '__main__':
    main()