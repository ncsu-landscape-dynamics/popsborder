# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from pathlib import Path


class DefaultPaths:

    def __init__(self):
        paths_file = Path(__file__)
        self.root = paths_file.parent.parent

    def slippage_data_dir(self) -> Path:
        return self.root / "development_files" / "slippage_data"

    def input_data_dir(self) -> Path:
        return self.root / "gui" / "data_input"

    def impact_data_dir(self) -> Path:
        return self.root / "impact_data"

    def output_dir(self) -> Path:
        return self.root / "output"

    def validation_output_dir(self) -> Path:
        return self.output_dir() / "validation_outputs"

    def prediction_model_compliance_dir(self) -> Path:
        return self.root / "Prediction_Model_Compliance_Tables"

    def tmp_dir(self) -> Path:
        """Root temporary data directory"""
        return self.root / "tmp"

    def compliance_dir(self) -> Path:
        """Directory for compliance lookup files"""
        compliance_path = self.tmp_dir() / "compliance"
        # Ensure directory exists
        compliance_path.mkdir(parents=True, exist_ok=True)
        return compliance_path
