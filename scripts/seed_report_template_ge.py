from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import ensure_schema, get_connection
from database.repositories.report_template_repository import insert_report_template
from models.report_template import ReportTemplate


def main() -> None:
    connection = get_connection()
    try:
        ensure_schema(connection)
        template = ReportTemplate(
            name="GE LogiqF Vascular Basic Template",
            facility_id=1,
            parser_family="ge_logiqf_vascular_sr",
            template_body=(
                "Paciente: {{ patient_name }} (ID: {{ patient_id }})\n"
                "Equipo: {{ manufacturer }}\n"
                "Institución: {{ institution_name }}\n\n"
                "PSV muestra: {{ concept_ln_11726_7 }}\n"
                "EDV muestra: {{ concept_ln_11653_3 }}\n"
                "Corrección angular muestra: {{ concept_99gems_geu_1004_9 }}\n"
                "ICA/CCA ratio muestra: {{ concept_ln_33868_1 }}\n"
            ),
            is_active=True,
        )
        template_id = insert_report_template(connection, template)
        connection.commit()
        print(f"Template creado: id={template_id}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
