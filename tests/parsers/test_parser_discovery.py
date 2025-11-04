import unittest

from custom_components.cable_modem_monitor.parsers.base_parser import ModemParser

class TestParserDiscovery(unittest.TestCase):
    def test_parser_sorting(self):
        ***REMOVED*** Create some mock parser classes
        class ArrisGenericParser(ModemParser):
            manufacturer = "Arris"
            priority = 50

        class MotorolaMB7621Parser(ModemParser):
            manufacturer = "Motorola"
            priority = 100

        class MotorolaGenericParser(ModemParser):
            manufacturer = "Motorola"
            priority = 50

        class TechnicolorGenericParser(ModemParser):
            manufacturer = "Technicolor"
            priority = 50

        parsers_to_sort = [
            ArrisGenericParser,
            MotorolaMB7621Parser,
            MotorolaGenericParser,
            TechnicolorGenericParser,
        ]

        ***REMOVED*** Sort the list using the same key as in get_parsers
        parsers_to_sort.sort(key=lambda p: (p.manufacturer, p.priority), reverse=True)

        sorted_parser_names = [p.__name__ for p in parsers_to_sort]

        expected_order = [
            "TechnicolorGenericParser",
            "MotorolaMB7621Parser",
            "MotorolaGenericParser",
            "ArrisGenericParser",
        ]

        self.assertEqual(sorted_parser_names, expected_order)

if __name__ == '__main__':
    unittest.main()