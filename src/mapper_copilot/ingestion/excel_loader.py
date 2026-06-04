"""Excel ingestion module for loading RSC and SLCP questions from Excel files."""

import logging
from pathlib import Path
from typing import List, Optional

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from mapper_copilot.models import ExcelColumnMap, RscQuestion, SlcpQuestion

logger = logging.getLogger(__name__)


class ExcelLoader:
    """Load RSC and SLCP questions from Excel files with configurable column mapping."""

    # Default column mappings (adjust these based on actual Excel structure)
    DEFAULT_RSC_COLUMN_MAP = ExcelColumnMap(
        id_column=0,  # Column A: question_id
        question_column=1,  # Column B: description
        section_column=2,  # Column C: section
        skip_rows=1,  # Skip 1 header row
    )

    DEFAULT_SLCP_COLUMN_MAP = ExcelColumnMap(
        id_column=0,  # Column A: slcp_key
        question_column=1,  # Column B: question
        section_column=2,  # Column C: section
        subsection_column=3,  # Column D: subsection
        skip_rows=1,  # Skip 1 header row
    )

    @staticmethod
    def load_rsc_questions(
        filepath: str, column_map: Optional[ExcelColumnMap] = None
    ) -> List[RscQuestion]:
        """
        Load RSC questions from Excel file.

        Args:
            filepath: Path to RSC Excel file
            column_map: Custom column mapping (uses DEFAULT_RSC_COLUMN_MAP if None)

        Returns:
            List of RscQuestion objects
        """
        column_map = column_map or ExcelLoader.DEFAULT_RSC_COLUMN_MAP
        return ExcelLoader._load_questions_from_excel(
            filepath,
            column_map,
            question_type="RSC",
            converter=ExcelLoader._row_to_rsc_question,
        )

    @staticmethod
    def load_slcp_questions(
        filepath: str, column_map: Optional[ExcelColumnMap] = None
    ) -> List[SlcpQuestion]:
        """
        Load SLCP questions from Excel file.

        Args:
            filepath: Path to SLCP Excel file
            column_map: Custom column mapping (uses DEFAULT_SLCP_COLUMN_MAP if None)

        Returns:
            List of SlcpQuestion objects
        """
        column_map = column_map or ExcelLoader.DEFAULT_SLCP_COLUMN_MAP
        return ExcelLoader._load_questions_from_excel(
            filepath,
            column_map,
            question_type="SLCP",
            converter=ExcelLoader._row_to_slcp_question,
        )

    @staticmethod
    def _load_questions_from_excel(
        filepath: str, column_map: ExcelColumnMap, question_type: str, converter
    ) -> List:
        """
        Generic loader for Excel questions.

        Args:
            filepath: Path to Excel file
            column_map: Column mapping configuration
            question_type: Type of question ("RSC" or "SLCP") for logging
            converter: Function to convert row data to domain object

        Returns:
            List of domain objects (RscQuestion or SlcpQuestion)
        """
        path = Path(filepath)
        if not path.exists():
            logger.error(f"{question_type} Excel file not found: {filepath}")
            raise FileNotFoundError(f"Excel file not found: {filepath}")

        logger.info(f"Loading {question_type} questions from {filepath}")

        try:
            wb = openpyxl.load_workbook(path, data_only=True)
            ws = wb.active
        except Exception as e:
            logger.error(f"Failed to load Excel file {filepath}: {e}")
            raise ValueError(f"Failed to load Excel file: {e}") from e

        questions = []
        for row_idx, row in enumerate(ws.iter_rows(min_row=1, values_only=False)):
            # Skip header rows
            if row_idx < column_map.skip_rows:
                continue

            try:
                # Extract cell values
                row_values = [cell.value if cell else None for cell in row]

                # Skip empty rows
                if not any(row_values):
                    continue

                # Convert to domain object
                obj = converter(row_values, column_map, row_idx + 1)  # 1-indexed
                if obj:
                    questions.append(obj)

            except Exception as e:
                logger.warning(f"Failed to parse row {row_idx + 1}: {e}")
                continue

        logger.info(f"Loaded {len(questions)} {question_type} questions")
        return questions

    @staticmethod
    def _row_to_rsc_question(row_values: list, column_map: ExcelColumnMap, row_num: int) -> Optional[RscQuestion]:
        """
        Convert Excel row to RscQuestion.

        Args:
            row_values: List of cell values from the row
            column_map: Column configuration
            row_num: Row number (for logging)

        Returns:
            RscQuestion object or None if parsing fails
        """
        try:
            question_id = row_values[column_map.id_column]
            description = row_values[column_map.question_column]

            if not question_id or not description:
                return None

            section = None
            if column_map.section_column is not None and column_map.section_column < len(row_values):
                section = row_values[column_map.section_column]

            return RscQuestion(
                question_id=str(question_id).strip(),
                key=str(question_id).strip(),
                description=str(description).strip(),
                section=str(section).strip() if section else None,
            )

        except (IndexError, ValueError, TypeError) as e:
            logger.debug(f"Could not parse RSC question from row {row_num}: {e}")
            return None

    @staticmethod
    def _row_to_slcp_question(row_values: list, column_map: ExcelColumnMap, row_num: int) -> Optional[SlcpQuestion]:
        """
        Convert Excel row to SlcpQuestion.

        Args:
            row_values: List of cell values from the row
            column_map: Column configuration
            row_num: Row number (for logging)

        Returns:
            SlcpQuestion object or None if parsing fails
        """
        try:
            slcp_key = row_values[column_map.id_column]
            question = row_values[column_map.question_column]

            if not slcp_key or not question:
                return None

            section = None
            if column_map.section_column is not None and column_map.section_column < len(row_values):
                section = row_values[column_map.section_column]

            subsection = None
            if column_map.subsection_column is not None and column_map.subsection_column < len(row_values):
                subsection = row_values[column_map.subsection_column]

            return SlcpQuestion(
                slcp_key=str(slcp_key).strip(),
                question=str(question).strip(),
                section=str(section).strip() if section else None,
                subsection=str(subsection).strip() if subsection else None,
            )

        except (IndexError, ValueError, TypeError) as e:
            logger.debug(f"Could not parse SLCP question from row {row_num}: {e}")
            return None
