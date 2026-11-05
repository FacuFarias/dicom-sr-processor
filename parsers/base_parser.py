from __future__ import annotations

from abc import ABC
from typing import Any

from models.extracted_variable import ExtractedVariable
from models.parser_manifest import ParserManifest


class BaseSRParser(ABC):
    parser_name = "BaseSRParser"
    parser_version = "1.0.0"
    parser_family = "base"
    supported_manufacturers = []
    supported_institutions = []
    supported_models = []
    supported_sop_class_uids = []
    supported_content_profiles = ["*"]
    compatibility_level = "strict"
    is_active = True

    @staticmethod
    def _normalize(value) -> str:
        if value is None:
            return "unknown"
        normalized = str(value).strip().lower().replace(" ", "_")
        return normalized or "unknown"

    def _matches(self, supported_values: list, fingerprint_value: str) -> bool:
        normalized_supported = [
            self._normalize(item) for item in (supported_values or ["*"])
        ]
        if "*" in normalized_supported:
            return True
        return self._normalize(fingerprint_value) in normalized_supported

    def can_parse(self, fingerprint: dict) -> bool:
        if not self.is_active:
            return False

        manufacturer_ok = self._matches(
            self.supported_manufacturers, fingerprint.get("manufacturer")
        )
        institution_ok = self._matches(
            self.supported_institutions, fingerprint.get("institution_name")
        )
        model_ok = self._matches(
            self.supported_models, fingerprint.get("manufacturer_model_name")
        )
        sop_ok = self._matches(
            self.supported_sop_class_uids, fingerprint.get("sop_class_uid")
        )
        content_profile_ok = self._matches(
            self.supported_content_profiles, fingerprint.get("content_profile")
        )

        return (
            manufacturer_ok
            and institution_ok
            and model_ok
            and sop_ok
            and content_profile_ok
        )

    def get_manifest(self) -> dict:
        manifest = ParserManifest(
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            parser_family=self.parser_family,
            supported_manufacturers=list(self.supported_manufacturers),
            supported_institutions=list(self.supported_institutions),
            supported_models=list(self.supported_models),
            supported_sop_class_uids=list(self.supported_sop_class_uids),
            compatibility_level=self.compatibility_level,
            is_active=bool(self.is_active),
        )
        return manifest.to_dict()

    def parse(self, dataset):
        return self.extract_content_sequence(dataset)

    @staticmethod
    def _to_serializable(value: Any):
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple)):
            return [BaseSRParser._to_serializable(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): BaseSRParser._to_serializable(item)
                for key, item in value.items()
            }
        if hasattr(value, "to_json_dict"):
            try:
                return value.to_json_dict()
            except Exception:
                pass
        if hasattr(value, "value"):
            return BaseSRParser._to_serializable(value.value)
        return str(value)

    @staticmethod
    def _safe_get(item: Any, attr_name: str):
        try:
            return getattr(item, attr_name, None)
        except Exception:
            return None

    def _build_variable_from_item(
        self,
        item: Any,
        dicom_path: str,
        sequence_index: int,
    ) -> ExtractedVariable:
        concept_code_value = None
        concept_code_scheme = None
        concept_code_meaning = None
        value_type = self._safe_get(item, "ValueType")
        value_text = self._safe_get(item, "TextValue")
        value_numeric = self._safe_get(item, "NumericValue")
        value_unit = None

        concept_name_sequence = self._safe_get(item, "ConceptNameCodeSequence")
        if concept_name_sequence:
            concept = concept_name_sequence[0]
            concept_code_value = self._safe_get(concept, "CodeValue")
            concept_code_scheme = self._safe_get(concept, "CodingSchemeDesignator")
            concept_code_meaning = self._safe_get(concept, "CodeMeaning")

        measured_value_sequence = self._safe_get(item, "MeasuredValueSequence")
        if measured_value_sequence:
            measured_value = measured_value_sequence[0]
            measured_numeric = self._safe_get(measured_value, "NumericValue")
            if measured_numeric is not None:
                value_numeric = measured_numeric

            measurement_units = self._safe_get(
                measured_value,
                "MeasurementUnitsCodeSequence",
            )
            if measurement_units:
                measurement_unit = measurement_units[0]
                value_unit = (
                    self._safe_get(measurement_unit, "CodeMeaning")
                    or self._safe_get(measurement_unit, "CodeValue")
                )

        raw_value = value_numeric if value_numeric is not None else value_text
        raw_item_json = self._to_serializable(item)

        return ExtractedVariable(
            dicom_tag="0040,A730",
            dicom_description="Content Sequence",
            dicom_path=dicom_path,
            concept_code_value=(
                str(concept_code_value) if concept_code_value is not None else None
            ),
            concept_code_scheme=(
                str(concept_code_scheme) if concept_code_scheme is not None else None
            ),
            concept_code_meaning=(
                str(concept_code_meaning) if concept_code_meaning is not None else None
            ),
            value_type=str(value_type) if value_type is not None else None,
            value_text=str(value_text) if value_text is not None else None,
            value_numeric=(
                float(value_numeric)
                if isinstance(value_numeric, (int, float))
                else (str(value_numeric) if value_numeric is not None else None)
            ),
            value_unit=str(value_unit) if value_unit is not None else None,
            sequence_index=sequence_index,
            raw_value=raw_value,
            raw_item_json=raw_item_json,
        )

    def extract_content_sequence(self, dataset) -> list[ExtractedVariable]:
        root_sequence = self._safe_get(dataset, "ContentSequence")
        if not root_sequence:
            return []

        extracted_variables: list[ExtractedVariable] = []

        def walk_sequence(sequence, base_path: str):
            for index, item in enumerate(sequence):
                current_path = f"{base_path}[{index}]"
                extracted_variables.append(
                    self._build_variable_from_item(
                        item=item,
                        dicom_path=current_path,
                        sequence_index=index,
                    )
                )

                nested_sequence = self._safe_get(item, "ContentSequence")
                if nested_sequence:
                    walk_sequence(nested_sequence, f"{current_path}.ContentSequence")

        walk_sequence(root_sequence, "ContentSequence")
        return extracted_variables
