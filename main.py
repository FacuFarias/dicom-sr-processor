from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from config.settings import settings
from core.fingerprint import build_fingerprint
from core.parser_loader import get_parser_manifests, load_parsers, resolve_parser
from database.connection import ensure_schema, get_connection
from database.repositories.parser_repository import (
    get_latest_parser_version,
    upsert_parser_manifest,
)
from database.repositories.report_template_repository import (
    get_active_template_for_parser_family,
    save_rendered_report,
)
from database.repositories.sr_document_repository import (
    insert_sr_document,
    mark_documents_for_reprocessing,
    update_sr_document_status,
)
from database.repositories.sr_variable_repository import insert_extracted_variables
from dicom.dicom_reader import read_dicom_dataset
from dicom.dicom_reader import read_dicom_metadata
from models.sr_document import SRDocument
from services.report_template_service import build_report_context, render_template
from services.variable_mapping_service import map_extracted_variables


def _resolve_facility_id(metadata: dict, facility_id: int | None = None) -> int:
    if facility_id is not None:
        return int(facility_id)
    return int(settings.default_facility_id)


def register_loaded_parsers(connection, parsers: list) -> int:
    manifests = get_parser_manifests(parsers)
    for manifest in manifests:
        upsert_parser_manifest(connection, manifest)
    print(f"Parsers registrados: {len(manifests)}")
    return len(manifests)


def check_reprocessing(connection, parsers: list) -> int:
    register_loaded_parsers(connection, parsers)

    manifests = get_parser_manifests(parsers)
    latest_by_family: dict[str, object] = {}
    for manifest in manifests:
        latest = get_latest_parser_version(connection, manifest.parser_family)
        if latest is not None:
            latest_by_family[manifest.parser_family] = latest

    total_marked = 0
    for family, latest_manifest in latest_by_family.items():
        marked = mark_documents_for_reprocessing(
            connection=connection,
            parser_family=family,
            new_version=latest_manifest.parser_version,
            compatibility_level=latest_manifest.compatibility_level,
        )
        total_marked += marked

    print(f"Documentos marcados para reproceso: {total_marked}")
    return total_marked


def process_sr_file(filepath: str, facility_id: int | None = None) -> dict:
    print(f"Archivo recibido: {filepath}")

    dataset = read_dicom_dataset(filepath)
    metadata = read_dicom_metadata(filepath)

    parsers = load_parsers()
    fingerprint = build_fingerprint(metadata)
    selected_parser = resolve_parser(fingerprint, parsers)
    resolved_facility_id = _resolve_facility_id(metadata, facility_id)

    print(f"Parsers cargados: {len(parsers)}")
    print(f"Facility ID: {resolved_facility_id}")
    print(f"Metadata: {metadata}")
    print(f"Fingerprint generado: {fingerprint['parser_key']}")
    print(
        "Parser seleccionado: "
        + (
            f"{selected_parser.parser_name} v{selected_parser.parser_version}"
            if selected_parser is not None
            else "None"
        )
    )

    connection = get_connection()
    sr_document_id = None
    started_at = datetime.now(timezone.utc)

    try:
        ensure_schema(connection)
        register_loaded_parsers(connection, parsers)

        sr_document = SRDocument(
            sop_instance_uid=metadata.get("sop_instance_uid"),
            study_instance_uid=metadata.get("study_instance_uid"),
            series_instance_uid=metadata.get("series_instance_uid"),
            sop_class_uid=metadata.get("sop_class_uid"),
            manufacturer=metadata.get("manufacturer"),
            manufacturer_model_name=metadata.get("manufacturer_model_name"),
            institution_name=metadata.get("institution_name"),
            station_name=metadata.get("station_name"),
            software_versions=metadata.get("software_versions"),
            parser_key=fingerprint.get("parser_key"),
            parser_name=(
                selected_parser.parser_name if selected_parser is not None else None
            ),
            parser_family=(
                selected_parser.parser_family if selected_parser is not None else None
            ),
            parser_version=(
                selected_parser.parser_version if selected_parser is not None else None
            ),
            raw_metadata_json={
                "metadata": metadata,
                "fingerprint": fingerprint,
                "dataset_summary": str(dataset.SOPClassUID)
                if hasattr(dataset, "SOPClassUID")
                else None,
            },
            status="received",
            processing_started_at=started_at,
        )

        sr_document_id = insert_sr_document(connection, sr_document)
        print(f"ID documento insertado: {sr_document_id}")

        if selected_parser is None:
            update_sr_document_status(connection, sr_document_id, "unsupported")
            connection.commit()
            print("Estado final del documento: unsupported")
            return {
                "sr_document_id": sr_document_id,
                "status": "unsupported",
                "variables_extracted": 0,
                "variables_saved": 0,
            }

        extracted_variables = selected_parser.parse(dataset)
        print(f"Variables extraídas: {len(extracted_variables)}")

        mapped_variables = map_extracted_variables(
            connection=connection,
            facility_id=resolved_facility_id,
            parser_key=fingerprint.get("parser_key"),
            variables=extracted_variables,
        )

        mapped_count = sum(
            1 for variable in mapped_variables if variable.mapping_status == "mapped"
        )
        unmapped_count = sum(
            1 for variable in mapped_variables if variable.mapping_status == "unmapped"
        )
        ambiguous_count = sum(
            1 for variable in mapped_variables if variable.mapping_status == "ambiguous"
        )

        print(f"Variables mapeadas: {mapped_count}")
        print(f"Variables no mapeadas: {unmapped_count}")
        print(f"Variables ambiguas: {ambiguous_count}")

        inserted_count = insert_extracted_variables(
            connection,
            sr_document_id,
            mapped_variables,
        )
        print(f"Cantidad de variables guardadas: {inserted_count}")

        rendered_report_id = None
        template = get_active_template_for_parser_family(
            connection=connection,
            facility_id=resolved_facility_id,
            parser_family=selected_parser.parser_family,
        )
        if template is not None:
            report_context = build_report_context(metadata, mapped_variables)
            rendered_text = render_template(template.template_body or "", report_context)
            rendered_report_id = save_rendered_report(
                connection=connection,
                sr_document_id=sr_document_id,
                template_id=template.id,
                rendered_text=rendered_text,
            )
            print(
                "Plantilla aplicada: "
                f"{template.name} (template_id={template.id}, rendered_id={rendered_report_id})"
            )
        else:
            print("No hay plantilla activa para esta facility/parser_family")

        update_sr_document_status(connection, sr_document_id, "processed")
        connection.commit()
        print(
            "Documento procesado con "
            f"parser_family={selected_parser.parser_family}"
        )
        print("Estado final del documento: processed")

        return {
            "sr_document_id": sr_document_id,
            "status": "processed",
            "variables_extracted": len(extracted_variables),
            "variables_saved": inserted_count,
            "variables_mapped": mapped_count,
            "variables_unmapped": unmapped_count,
            "variables_ambiguous": ambiguous_count,
            "rendered_report_id": rendered_report_id,
        }
    except Exception as exc:
        connection.rollback()
        print(f"Error durante procesamiento: {exc}")

        if sr_document_id is not None:
            try:
                update_sr_document_status(
                    connection,
                    sr_document_id,
                    "failed",
                    error_message=str(exc),
                )
                connection.commit()
                print("Estado final del documento: failed")
            except Exception as status_exc:
                connection.rollback()
                print(f"No se pudo actualizar estado failed: {status_exc}")

        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="DICOM SR Processor")
    parser.add_argument("filepath", nargs="?", default=None, help="Ruta del archivo DICOM SR")
    parser.add_argument(
        "--facility-id",
        type=int,
        default=None,
        help="Facility ID para resolver mappings",
    )
    parser.add_argument(
        "--check-reprocessing",
        action="store_true",
        help="Revisa documentos históricos y marca needs_reprocessing",
    )
    args = parser.parse_args()

    print("SR Processor iniciado")
    if args.check_reprocessing:
        connection = get_connection()
        try:
            ensure_schema(connection)
            parsers = load_parsers()
            marked = check_reprocessing(connection, parsers)
            connection.commit()
            result = {"documents_marked_for_reprocessing": marked}
        finally:
            connection.close()
    else:
        if not args.filepath:
            raise ValueError("Debe indicar filepath o usar --check-reprocessing")
        result = process_sr_file(args.filepath, facility_id=args.facility_id)

    print(f"Resultado: {json.dumps(result, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
