import os
import math
import numpy as np
import pickle
from tqdm import tqdm
import matplotlib.pyplot as plt

import json
import nibabel as nib

from skimage.segmentation import clear_border

from utils.preprocess import Patient


"""" This file does the following: 
    
    1. Create two folders named 'scans' and 'masks' in OUTPUT_DIR.

    2. From INPUT_DIR and MAX_DEPTH, construct a list of tuple (json_path, nifti_path),
       with the files being chosen as both annotated and not to deep. 
    
    3. STEP 1: For each selected scan, construct a mask by doing a logical AND between a mask obtained 
       by thresholding (130 HU) and one obtained by dilating around annotations coordinates.
       Store the mask in OUTPUT_DIR/masks/ as .npy.

    4. STEP 2: For each selected scan and its associated mask, crop in 3d based on mean intensity values.
       Store the cropped scans in OUTPUT_DIR/scans/ and the cropped scans in OUTPUT_DIR/masks/ as .npy. 

    This 4 things are wrapped into one function.
    This fonction can take a list of steps to execute.
"""



class Preprocess:

    def __init__(self, input_dir, output_dir, max_depth):

        self.input_dir      = input_dir
        self.output_dir     = output_dir
        # dataset_paths is a list of tuple [(json_path, nifti_path)]
        self.dataset_paths  = self.get_dataset_paths(max_depth)
        # output_paths is a list of tuple [(scan_array_path, mask_array_path)]
        self.output_paths   = self.get_output_paths()


    def get_good_json_paths(self):
        """ Some jsons have class annotations but no localisations info.
            We can't use them for segmentation, hence we drop their paths.
        """
        all_json_files = list(filter(lambda x: x.endswith(".json"), os.listdir(self.input_dir)))
        all_json_paths = list(map(lambda x: os.path.join(self.input_dir, x), all_json_files))
        good_json_paths = []
        for json_path in all_json_paths:
            with open(json_path) as json_file:
                data = json.load(json_file)
                if len(data.keys()) > 2:
                    good_json_paths.append(json_path)
        return good_json_paths


    def select_one_nifti_path(self, json_path, all_paths, max_depth):
        """ One scan is sometimes associated with several nifti images.
            We select the deepest one being smaller than max_depth.
        """
        nifti_candidates = list(filter(lambda x: x.startswith(json_path[:-5]) and x.endswith(".nii.gz"), all_paths))
        max_z = 1
        final_nifti_path = nifti_candidates[0]
        for nifti_path in nifti_candidates:
            z = nib.load(nifti_path).header.get_data_shape()[2]
            if max_z < z < max_depth:
                max_z = nib.load(nifti_path).header.get_data_shape()[2]
                final_nifti_path = nifti_path
        return final_nifti_path


    def get_dataset_paths(self, max_depth):
        """ Takes an input dir and return a list of tuple (json_path, nifti_path). """
        dataset_paths = []
        all_paths = list(map(lambda x: os.path.join(self.input_dir, x), os.listdir(self.input_dir)))
        good_json_paths = self.get_good_json_paths()
        for json_path in good_json_paths:
            nifti_path = self.select_one_nifti_path(json_path, all_paths, max_depth)
            dataset_paths.append((json_path,nifti_path))
        return dataset_paths


    def prepare_output_folders(self):
        """ Create output folder and subfolders if needed. """
        if not os.path.isdir(self.output_dir):
            os.mkdir(self.output_dir)
        preprocessed_scans_dir = os.path.join(self.output_dir, 'scans')
        preprocessed_masks_dir = os.path.join(self.output_dir, 'masks')  
        if not os.path.isdir(preprocessed_scans_dir):
            os.mkdir(preprocessed_scans_dir)
        if not os.path.isdir(preprocessed_masks_dir):
            os.mkdir(preprocessed_masks_dir)


    def get_output_paths(self):
        """ Generates a list of tuple [(preprocessed_scan_path, preprocessed_mask_path)]"""
        output_paths = []
        for paths in self.dataset_paths:
            scan_name = paths[1][len(self.input_dir):-7]
            output_scan_path = os.path.join(self.output_dir, 'scans/', scan_name + '.npy')
            output_mask_path = os.path.join(self.output_dir, 'masks/', scan_name + '.npy')
            output_paths.append((output_scan_path, output_mask_path))
        return output_paths


    def step1(self, cube_side):
        """ Make and store masks (uncropped) in OUTPUT_DIR/masks/ ."""
        for i in tqdm(range(len(self.dataset_paths))):
            json_path, nifti_path = self.dataset_paths[i] 
            patient = Patient(json_path, nifti_path)
            output_mask_path = self.output_paths[i][1]
            patient.make_mask(cube_side)
            patient.save_mask(output_mask_path)


    def step2(self, factor):
        """ Crop scans a masks and store the outputs respectively in 
            OUTPUT_DIR/scans and OUTPUT_DIR/masks/ .
        """
        for i in tqdm(range(len(self.dataset_paths))):
            output_scan_path, mask_path = self.output_paths[i][0], self.output_paths[i][1]
            patient = Patient(self.dataset_paths[i][0], self.dataset_paths[i][1])
            patient.load_mask(mask_path)
            patient.rescale('up') 
            patient.crop_3d(factor)
            patient.rescale('down') 
            patient.save_scan(output_scan_path)
            patient.save_mask(mask_path)


    def preprocess_dataset(self, steps, cube_side=10, factor=2):
        self.prepare_output_folders()
        if 1 in steps:
            print("STEP 1: Creating Masks...")
            self.step1(cube_side)
        if 2 in steps:
            print("STEP 2: Cropping Scans & Masks...")
            self.step2(factor)