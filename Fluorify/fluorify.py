#!/usr/bin/env python

from .energy import FSim
from .mol2 import Mol2, MutatedLigand

import os
import time
import mdtraj as md


class Scanning(object):
    def __init__(self, input_folder, output_folder, mol_file, ligand_name,
                 complex_name, solvent_name, job_type, exclusion_list):
        """A class for preparation and running scanning analysis

        input_folder: name for input directory. Default, input
        mol_file: name of input ligand file
        ligand_name: resname for input ligand
        complex_name: name of complex phase directory inside of input directory. Default, complex
        solvent_name: name of solvent phase directory inside of output directory.  Default solvent
        job_type: name of scanning requested i.e. F_ar replaces hydrogen on aromatic 'ar' carbons with fluorine 'F'
        exclusion_list: list of atoms to exclude from being replaced (not implemented)
        output_folder: name for output directory. Default, mol_file + job_type
        """
        self.job_type = job_type

        #Prepare directories/files and read in ligand from mol2 file
        mol_file = mol_file + '.mol2'
        complex_sim_dir = input_folder + complex_name + '/'
        solvent_sim_dir = input_folder + solvent_name + '/'

        if os.path.isdir(output_folder):
            print('Output folder {} already exists.'
                  ' Will attempt to skip ligand parametrisation, proceed with caution...'.format(output_folder))
        else:
            try:
                os.makedirs(output_folder)
            except:
                print('Could not create output folder {}'.format(output_folder))

        self.mol = Mol2()
        try:
            Mol2.get_data(self.mol, input_folder, mol_file)
        except:
            raise ValueError('Could not load molecule {}'.format(input_folder + mol_file))

        #Check ligand atom order is consistent across input topologies.
        mol2_ligand_atoms = get_atom_list(input_folder+mol_file, ligand_name)
        complex_ligand_atoms = get_atom_list(complex_sim_dir+complex_name+'.pdb', ligand_name)
        solvent_ligand_atoms = get_atom_list(solvent_sim_dir+solvent_name+'.pdb', ligand_name)
        if mol2_ligand_atoms != complex_ligand_atoms:
            raise ValueError('Topology of ligand not matched across input files.'
                             'Charges will not be applied where expected')
        if complex_ligand_atoms != solvent_ligand_atoms:
            raise ValueError('Topology of ligand not matched across input files.'
                             'Charges will not be applied where expected')

        #Generate atom selections
        if self.job_type[0] == 'N.ar':
            mutated_systems, target_atoms = Scanning.add_nitrogens(self, exclusion_list)
        else:
            mutated_systems, target_atoms = Scanning.add_fluorines(self, exclusion_list)

        """
        Write Mol2 files with substitutions of selected atoms.
        Run antechamber and tleap on mol2 files to get prmtop.
        Create OpenMM systems of ligands from prmtop files.
        Extract ligand charges from OpenMM systems.
        """
        print('Parametrize mutant ligands...')
        t0 = time.time()

        mutated_ligands = []
        for index, sys in enumerate(mutated_systems):
            Mol2.write_mol2(sys, output_folder, 'molecule'+str(index))
            mutated_ligands.append(MutatedLigand(file_path=output_folder,
                                                 file_name='{}.mol2'.format('molecule'+str(index))))

        ligand_charges = []
        for ligand in mutated_ligands:
            ligand_charges.append(ligand.get_charge())

        t1 = time.time()
        print('Took {} seconds'.format(t1 - t0))

        """
        Build OpenMM simulations for complex and solvent phases.
        Apply ligand charges to OpenMM simulations.
        Calculate potential energy of simulation with mutant charges.
        Calculate free energy change from wild type to mutant.
        """
        print('Calculating free energies...')
        t0 = time.time()

        #COMPLEX
        complex = FSim(ligand_name=ligand_name, sim_name=complex_name, input_folder=input_folder)
        com_top = md.load(complex_sim_dir+complex_name+'.pdb').topology
        com_dcd = complex_sim_dir + complex_name + '.dcd'
        #SOLVENT
        solvent = FSim(ligand_name=ligand_name, sim_name=solvent_name, input_folder=input_folder)
        sol_top = md.load(solvent_sim_dir+solvent_name+'.pdb').topology
        sol_dcd = solvent_sim_dir + solvent_name + '.dcd'

        complex_free_energy = FSim.treat_phase(complex, ligand_charges, com_dcd, com_top)
        print(complex_free_energy)
        solvent_free_energy = FSim.treat_phase(solvent, ligand_charges, sol_dcd, sol_top)
        print(solvent_free_energy)

        for i, energy in enumerate(complex_free_energy):
            atom_index = int(target_atoms[i])-1
            print('dG for molecule{}.mol2 with'
                  ' {} substituted for {}'.format(str(i), mol2_ligand_atoms[atom_index], job_type[0]))
            print(energy - solvent_free_energy[i])

        t1 = time.time()
        print('Took {} seconds'.format(t1 - t0))

    def add_fluorines(self, exclusion_list):
        exclusion_list = ['34', '35', '36', '37', '38', '39', '40', '41', '42', '43', '44', '45',
                          '46', '47', '48', '49', '50', '51', '52', '53', '54', '55', '56', '57', '58']
        new_element = self.job_type[0]
        carbon_type = 'C.' + self.job_type[1]
        carbons = Mol2.get_atom_by_string(self.mol, carbon_type)
        hydrogens = Mol2.get_atom_by_string(self.mol, 'H')
        tmp = [x for x in hydrogens if x not in exclusion_list]
        if len(exclusion_list) != 0:
            if tmp == hydrogens:
                raise ValueError('An exclusion list was specified for {} scanning but the list did not reference any'
                                 ' hydrogen in the system to excluded from being replaced'.format(self.job_type[0]))
            else:
                hydrogens = tmp
        carbons_neighbours = Mol2.get_bonded_neighbours(self.mol, carbons)
        bonded_h = [x for x in hydrogens if x in carbons_neighbours]
        mutated_systems = Mol2.mutate_elements(self.mol, bonded_h, new_element)
        return mutated_systems, bonded_h

    def add_nitrogens(self, exclusion_list):
        """
        Look for carbons with one hydrogen neighbour.
        Reduce list of carbons to those with one hydrogen neighbour.
        Make a note of which hydrogen is the neighbour.
        Swap the carbon for a nitrogen and hydrogen for dummy.
        This should be making Pyridine.
        """
        # Du (dummy atom) is not recognised by antechamber but it throws no errors
        # this is not a viable method
        new_element = self.job_type[0]
        carbon_type = 'C.' + self.job_type[1]
        carbons = Mol2.get_atom_by_string(self.mol, carbon_type)
        tmp = [x for x in carbons if x not in exclusion_list]
        if len(exclusion_list) != 0:

            if tmp == carbons:
                raise ValueError('An exclusion list was specified for N scanning but the list '
                                 'did not reference any carbon in the system to excluded from being replaced')
            else:
                carbons = tmp
        hydrogens = Mol2.get_atom_by_string(self.mol, 'H')
        hydrogens_to_remove = []
        c_tmp = []
        for atom in carbons:
            h_tmp = []
            neighbours = Mol2.get_bonded_neighbours(self.mol, atom)
            for neighbour in neighbours:
                if neighbour in hydrogens:
                    h_tmp.append(neighbour)
            if len(h_tmp) == 1:
                hydrogens_to_remove.append(h_tmp[0])
                c_tmp.append(atom)
        carbons = c_tmp

        nitrogen_mutated_systems = Mol2.mutate_elements(self.mol, carbons, new_element)
        mutated_systems = []
        for i, mutant in enumerate(nitrogen_mutated_systems):
            mutated_systems.append(Mol2.mutate_one_element(mutant, hydrogens_to_remove[i], 'Du'))
        return mutated_systems, carbons


def get_atom_list(file, resname):
    atoms = []
    traj = md.load(file)
    top = traj.topology
    mol = top.select('resname '+resname)
    for idx in mol:
        atoms.append(str(top.atom(idx)).split('-')[1])
    return atoms

