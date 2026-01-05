"""DMRG input plugin."""

from aiida.common import CalcInfo, CodeInfo
from aiida.engine import CalcJob
from aiida.engine.processes.process_spec import CalcJobProcessSpec
from aiida.orm import Dict, RemoteData


class DMRGCalculation(CalcJob):
    """
    AiiDA calculation plugin for the DMRG code.

    """

    INPUT_FILE = "dmrg.inp"
    OUTPUT_FILE = "dmrg.out"
    PARENT_FOLDER_NAME = "parent_calc"
    DEFAULT_PARSER = "dmrg.base"

    @classmethod
    def define(cls, spec: CalcJobProcessSpec):
        super().define(spec)

        # Input parameters
        spec.input(
            "parameters",
            valid_type=Dict,
            required=True,
            help="Input parameters for the DMRG calculation",
        )

        spec.input(
            "parent_calc_folder",
            valid_type=RemoteData,
            required=False,
            help="the folder of a completed dmrg calculation",
        )

        spec.input("metadata.options.withmpi", valid_type=bool, default=True)

        spec.input(
            "metadata.options.parser_name",
            valid_type=str,
            default=cls.DEFAULT_PARSER,
            non_db=True,
        )

        # Outputs
        spec.output(
            "output_parameters",
            valid_type=Dict,
            required=True,
            help="The results of the calculation",
        )

        spec.output(
            "Hamiltonian_sites",
            valid_type=Dict,
            required=False,
            help="""Sites and Hamiltonian of
            the system for dynamical correlator""",
        )

        spec.output(
            "remote_folder",
            valid_type=RemoteData,
            required=True,
            help="The folder of the remote calculation",
        )

        spec.default_output_node = "output_parameters"
        spec.outputs.dynamic = True

        spec.exit_code(
            200,
            "ERROR_NO_RETRIEVED_FOLDER",
            message="The retrieved folder data node could not be accessed.",
        )
        spec.exit_code(
            201,
            "ERROR_READING_INPUT_FILE",
            message="The input file could not be read or misses some values.",
        )
        spec.exit_code(
            202,
            "ERROR_UNPHYISCAL_INPUT",
            message="""The input file contains unphysical
            values (check s, N and Sz).""",
        )
        spec.exit_code(
            203,
            "ERROR_J_VALUE",
            message="The J value / matrix in the input file is not correct.",
        )
        spec.exit_code(
            210,
            "ERROR_OUTPUT_MISSING",
            message="There is some data missing in the output file.",
        )
        spec.exit_code(
            211,
            "ERROR_OUTPUT_LOG_READ",
            message="The retrieved output log could not be read.",
        )
        spec.exit_code(
            312,
            "ERROR_HDF5_WRITE",
            message="Failed to write HDF5 output files.",
        )
        spec.exit_code(
            390,
            "ERROR_TERMINATION",
            message="The calculation was terminated due to an error.",
        )

    def prepare_for_submission(self, folder):
        """
        This is the routine to be called when you want to create
        the input files and related stuff with a plugin.

        :param folder: a aiida.common.folders.Folder subclass where
                        the plugin should put all its files.
        """
        # Get the settings dictionary, or an empty one if not specified

        # Generate the input file
        input_string = DMRGCalculation._render_input_string_from_params(
            self.inputs.parameters.get_dict()
        )

        with open(folder.get_abs_path(self.INPUT_FILE), "w") as out_file:
            out_file.write(input_string)

        settings = (
            self.inputs.get("settings", {}).get_dict()
            if "settings" in self.inputs
            else {}
        )

        codeinfo = CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.cmdline_params = settings.pop("cmdline", [])
        codeinfo.stdin_name = self.INPUT_FILE
        codeinfo.stdout_name = self.OUTPUT_FILE
        codeinfo.stderr_name = self.OUTPUT_FILE
        codeinfo.withmpi = self.inputs.metadata.options.withmpi

        # create calculation info
        calcinfo = CalcInfo()
        calcinfo.remote_copy_list = []
        calcinfo.local_copy_list = []
        calcinfo.uuid = self.uuid
        calcinfo.cmdline_params = codeinfo.cmdline_params
        calcinfo.stdin_name = self.INPUT_FILE
        calcinfo.stdout_name = self.OUTPUT_FILE
        calcinfo.stderr_name = self.OUTPUT_FILE
        calcinfo.codes_info = [codeinfo]
        calcinfo.retrieve_list = [self.OUTPUT_FILE]

        # symlink or copy to parent calculation
        calcinfo.remote_symlink_list = []
        calcinfo.remote_copy_list = []
        if "parent_calc_folder" in self.inputs:
            comp_uuid = self.inputs.parent_calc_folder.computer.uuid
            remote_path = self.inputs.parent_calc_folder.get_remote_path()
            copy_info = (comp_uuid, remote_path, self.PARENT_FOLDER_NAME)
            if self.inputs.code.computer.uuid == comp_uuid:
                calcinfo.remote_symlink_list.append(copy_info)
            else:
                calcinfo.remote_copy_list.append(copy_info)

        calcinfo.retrieve_list.append(self.PARENT_FOLDER_NAME)

        return calcinfo

    @classmethod
    def _render_input_string_from_params(cls, parameters):
        """Convert dictionary parameters to Julia command line arguments"""
        param_order = [
            "S",
            "N_sites",
            "cutoff",
            "J",
            "Sz",
            "n_excitations",
            "conserve_symmetry",
            "print_HDF5",
            "maximal_energy",
        ]
        ordered_params = []
        for key in param_order:
            if key in parameters:
                value = parameters[key]
                ordered_params.append(f"{value}")

        return " ".join(ordered_params)
