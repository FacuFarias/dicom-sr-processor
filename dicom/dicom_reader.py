from __future__ import annotations

from pathlib import Path


try:
    import pydicom
    from pydicom.errors import InvalidDicomError
except ImportError:  # pragma: no cover
    pydicom = None
    InvalidDicomError = Exception


def read_dicom(file_path: str | Path):
    if pydicom is None:
        raise RuntimeError("pydicom no está instalado en el entorno actual")

    return pydicom.dcmread(str(file_path))


def read_dicom_dataset(filepath: str):
    if pydicom is None:
        raise RuntimeError("pydicom no está instalado en el entorno actual")

    try:
        return pydicom.dcmread(filepath)
    except FileNotFoundError as exc:
        raise ValueError(f"Archivo DICOM no encontrado: {filepath}") from exc
    except InvalidDicomError as exc:
        raise ValueError(f"Archivo DICOM inválido: {filepath}") from exc
    except Exception as exc:
        raise ValueError(f"No se pudo leer el archivo DICOM: {exc}") from exc


def read_dicom_metadata(filepath: str) -> dict:
    dataset = read_dicom_dataset(filepath)

    def read_tag(tag_name: str):
        value = getattr(dataset, tag_name, None)
        return str(value) if value is not None else None

    def _detect_content_profile() -> str:
        content_sequence = getattr(dataset, "ContentSequence", None)
        if not content_sequence:
            return "generic_sr"

        concept_pairs: set[tuple[str, str]] = set()

        def walk(sequence):
            for item in sequence or []:
                concept_name_sequence = getattr(item, "ConceptNameCodeSequence", None)
                if concept_name_sequence:
                    concept = concept_name_sequence[0]
                    code_value = getattr(concept, "CodeValue", None)
                    code_scheme = getattr(concept, "CodingSchemeDesignator", None)
                    concept_pairs.add(
                        (
                            str(code_value) if code_value is not None else "",
                            str(code_scheme) if code_scheme is not None else "",
                        )
                    )

                nested = getattr(item, "ContentSequence", None)
                if nested:
                    walk(nested)

        walk(content_sequence)

        if (
            ("11726-7", "LN") in concept_pairs
            and ("11653-3", "LN") in concept_pairs
        ):
            return "vascular_doppler_sr"

        if any(code_scheme == "99GEMS" for _, code_scheme in concept_pairs):
            return "ge_us_private_params"

        return "generic_sr"

    return {
        "patient_name": read_tag("PatientName"),
        "patient_id": read_tag("PatientID"),
        "patient_sex": read_tag("PatientSex"),
        "patient_birth_date": read_tag("PatientBirthDate"),
        "manufacturer": read_tag("Manufacturer"),
        "institution_name": read_tag("InstitutionName"),
        "manufacturer_model_name": read_tag("ManufacturerModelName"),
        "station_name": read_tag("StationName"),
        "software_versions": read_tag("SoftwareVersions"),
        "completion_flag": read_tag("CompletionFlag"),
        "verification_flag": read_tag("VerificationFlag"),
        "content_date": read_tag("ContentDate"),
        "content_time": read_tag("ContentTime"),
        "sop_class_uid": read_tag("SOPClassUID"),
        "sop_instance_uid": read_tag("SOPInstanceUID"),
        "study_instance_uid": read_tag("StudyInstanceUID"),
        "series_instance_uid": read_tag("SeriesInstanceUID"),
        "content_profile": _detect_content_profile(),
    }
