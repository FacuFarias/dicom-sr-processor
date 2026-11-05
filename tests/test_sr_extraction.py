from parsers.example_parser import ExampleParser


class Node:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _build_sr_dataset_with_content():
    concept = Node(
        CodeValue="12345",
        CodingSchemeDesignator="DCM",
        CodeMeaning="Heart Rate",
    )
    unit = Node(CodeValue="/min", CodeMeaning="bpm")
    measured = Node(
        NumericValue=72,
        MeasurementUnitsCodeSequence=[unit],
    )

    nested_item = Node(
        ValueType="TEXT",
        TextValue="Nested observation",
        ConceptNameCodeSequence=[
            Node(
                CodeValue="777",
                CodingSchemeDesignator="99TEST",
                CodeMeaning="Nested Meaning",
            )
        ],
    )

    item = Node(
        ValueType="NUM",
        ConceptNameCodeSequence=[concept],
        MeasuredValueSequence=[measured],
        ContentSequence=[nested_item],
    )

    return Node(ContentSequence=[item])


def test_parser_returns_list_when_content_sequence_exists():
    parser = ExampleParser()
    dataset = _build_sr_dataset_with_content()

    variables = parser.parse(dataset)

    assert isinstance(variables, list)
    assert len(variables) >= 1


def test_concept_fields_are_extracted_from_concept_name_code_sequence():
    parser = ExampleParser()
    dataset = _build_sr_dataset_with_content()

    variables = parser.parse(dataset)
    first = variables[0]

    assert first.concept_code_value == "12345"
    assert first.concept_code_scheme == "DCM"
    assert first.concept_code_meaning == "Heart Rate"


def test_measured_value_sequence_extracts_numeric_and_unit():
    parser = ExampleParser()
    dataset = _build_sr_dataset_with_content()

    variables = parser.parse(dataset)
    first = variables[0]

    assert first.value_numeric == 72.0
    assert first.value_unit == "bpm"


def test_every_extracted_variable_has_dicom_path():
    parser = ExampleParser()
    dataset = _build_sr_dataset_with_content()

    variables = parser.parse(dataset)

    assert len(variables) >= 2
    for variable in variables:
        assert variable.dicom_path


def test_parser_returns_empty_list_when_no_content_sequence():
    parser = ExampleParser()
    dataset = Node()

    variables = parser.parse(dataset)

    assert variables == []
