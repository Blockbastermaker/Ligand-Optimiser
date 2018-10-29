#!/usr/bin/env python

import os
import logging
import openmoltools as moltool
import simtk.openmm as mm


class Mol2(object):
    def __init__(self, molecule=None, atoms=None, bonds=None, other=None):
        """A class for reading, writing and modifying a ligand in a mol2 file.

        molecule: All information in mol2 file under '@<TRIPOS>MOLECULE' header
        atoms: All information in mol2 file under '@<TRIPOS>ATOM' header
        bonds: All information in mol2 file under '@<TRIPOS>BOND' header
        other: All information in mol2 file not under MOLECULE, ATOM or BOND header
        """
        self.data = {'MOLECULE': [], 'ATOM': [], 'BOND': [], 'OTHER': []}
        Mol2.update_data(self, molecule, atoms, bonds, other)

    def get_data(self, ligand_file_path, ligand_file_name):
        ligand = open(ligand_file_path+ligand_file_name)
        data = {'MOLECULE': [], 'ATOM': [], 'BOND': [], 'OTHER': []}
        headers = ['@<TRIPOS>MOLECULE', '@<TRIPOS>ATOM', '@<TRIPOS>BOND']
        key = None
        for line in ligand:
            if line[0] == '@':
                line = line.strip('\n')
                if line == '@<TRIPOS>MOLECULE':
                    key = 'MOLECULE'
                elif line == '@<TRIPOS>ATOM':
                    key = 'ATOM'
                elif line == '@<TRIPOS>BOND':
                    key = 'BOND'
                else:
                    key = 'OTHER'
            if line not in headers:
                data[key].append(line)
        self.data = data

    def write_mol2(self, file_path, file_name):
        mol2 = []
        headers = {'MOLECULE': '@<TRIPOS>MOLECULE\n', 'ATOM': '@<TRIPOS>ATOM\n', 'BOND': '@<TRIPOS>BOND\n', 'OTHER': ''}
        for k, v in self.data.items():
            mol2.append(headers[k])
            for line in v:
                mol2.append(line)
        f = open(file_path+file_name+'.mol2', 'w')
        for line in mol2:
            f.write(line)
        f.close()

    def update_data(self, molecule, atoms, bonds, other):
        data = {'MOLECULE': molecule, 'ATOM': atoms, 'BOND': bonds, 'OTHER': other}
        self.data = data

    def get_atom_by_string(self, string):
        if self.data == None:
            logger.error('No data to search. Please use get_data() first')
        atoms = []
        for line in self.data['ATOM']:
            if line.split()[5] == string:
                atoms.append(line.split()[0])
        err_msg = 'Atom selection {} not recognised or atoms of this type are not in ligand'.format(string)
        if len(atoms) == 0:
            logging.error(err_msg)
        return atoms

    def get_bonded_neighbours(self, atoms=[]):
        neighbours = []
        for line in self.data['BOND']:
            if line.split()[1] in atoms:
                neighbours.append(line.split()[2])
        return neighbours

    """
    def remove_atom(self, atom):
        if atom == None:
            return
        new_atom_data = []

        for line in self.data['ATOM']:
            if int(line.split()[0]) is int(atom):
                print(line)
            else:
                new_atom_data.append(line)

        Mol2.update_data(self, molecule=self.data['MOLECULE'], atoms=new_atom_data,
                         bonds=self.data['BOND'], other=self.data['OTHER'])

    def remove_bonds(self, atom):
        if atom == None:
            return
        new_bond_data = []

        for line in self.data['BOND']:
            if int(line.split()[1]) is int(atom):
                print(line)
            elif int(line.split()[2]) is int(atom):
                print(line)
            else:
                new_bond_data.append(line)

        Mol2.update_data(self, molecule=self.data['MOLECULE'], atoms=self.data['ATOM'],
                         bonds=new_bond_data, other=self.data['OTHER'])
    """

    def mutate_one_element(self, atom, new_element):
        new_atom_data = []
        new_element = new_element.split('.')

        if len(new_element) > 1:
            tmp = new_element[0]
            new_element[0] = new_element[0] + '.' + new_element[1]
            new_element[1] = tmp

        for line in self.data['ATOM']:
            old_element = []
            if int(line.split()[0]) is int(atom):
                old_element.append(str(line.split()[5]))
                s = str(line.split()[1])
                old_element.append(''.join([i for i in s if not i.isdigit()]))
                for i, entry in enumerate(new_element):
                    line = line.replace(old_element[i], entry)
                new_atom_data.append(line)
            else:
                new_atom_data.append(line)

        return Mol2(molecule=self.data['MOLECULE'], atoms=new_atom_data,
                    bonds=self.data['BOND'], other=self.data['OTHER'])

    def mutate_elements(self, atoms, new_element):
        mutated_systems = []
        for atom in atoms:
            mutated_system = Mol2.mutate_one_element(self, atom, new_element)
            mutated_systems.append(mutated_system)
        return mutated_systems


class MutatedLigand(object):
    def __init__(self, file_path, file_name):
        """A class for extracting parameters from a mutated ligand in a mol2 file.
        file_path: location of ligand file
        file_name: name of ligand file
        """
        name, extension = os.path.splitext(file_name)
        if extension == '.mol2':
            run_ante(file_path, file_name, name)
            MutatedLigand.create_system(self, file_path, name)
        else:
            logging.error('Input {} not found or incorrect format'.format(file_path + file_name))

    def create_system(self, file_path, name):
        parameters_file_path = file_path + name + '.prmtop'
        parameters_file = mm.app.AmberPrmtopFile(parameters_file_path)
        self.system = parameters_file.createSystem()

    def get_charge(self):
        system = self.system
        ligand_charge = []
        for force in system.getForces():
            if isinstance(force, mm.NonbondedForce):
                nonbonded_force = force
        for index in range(system.getNumParticles()):
            charge, sigma, epsilon = nonbonded_force.getParticleParameters(index)
            ligand_charge.append(charge)
        return (ligand_charge)

    def get_other_particleparameters():
        pass


def run_ante(file_path, file_name, name):
    if os.path.exists(file_path+name+'.prmtop'):
        print('{0} found skipping antechamber and tleap for {1}'.format(file_path+name+'.prmtop', name))
    else:
        moltool.amber.run_antechamber(molecule_name=file_path+name, input_filename=file_path+file_name)
        moltool.amber.run_tleap(molecule_name=file_path+name, gaff_mol2_filename=file_path+name+'.gaff.mol2',
                                frcmod_filename=file_path+name+'.frcmod')