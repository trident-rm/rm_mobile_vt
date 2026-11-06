from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from vt13_video.nal import (
    AccessUnitAssembler,
    AnnexBParser,
    PARAMETER_SET_TYPES,
    ParameterSetCache,
    scan_nals,
)

from .helpers import make_nal


class AnnexBParserTests(unittest.TestCase):
    def test_parser_handles_arbitrary_chunk_boundaries(self) -> None:
        nals = [
            make_nal(32, b"\x01", start_code=b"\x00\x00\x00\x01"),
            make_nal(33, b"\x02"),
            make_nal(34, b"\x03", start_code=b"\x00\x00\x00\x01"),
            make_nal(35, b"\x30"),
            make_nal(1, b"\x00", first_slice=True),
            make_nal(40, b"\x05"),
        ]
        data = b"leading-garbage" + b"".join(nals)

        for chunk_size in (1, 2, 3, 4, 5, 7, 11, 64, len(data)):
            with self.subTest(chunk_size=chunk_size):
                parser = AnnexBParser()
                parsed = []
                for offset in range(0, len(data), chunk_size):
                    parsed.extend(parser.feed(data[offset : offset + chunk_size]))
                parsed.extend(parser.flush())

                self.assertEqual([nal.raw for nal in parsed], nals)
                self.assertEqual([nal.nal_type for nal in parsed], [32, 33, 34, 35, 1, 40])
                self.assertEqual(parser.discarded_prefix_bytes, len(b"leading-garbage"))
                self.assertEqual(parser.invalid_nals, 0)

    def test_invalid_nal_header_is_counted(self) -> None:
        parser = AnnexBParser()
        invalid = b"\x00\x00\x01\x80\x01payload"
        self.assertEqual(parser.feed(invalid), [])
        self.assertEqual(parser.flush(), [])
        self.assertEqual(parser.invalid_nals, 1)


class AccessUnitAssemblerTests(unittest.TestCase):
    def _feed_all(self, assembler: AccessUnitAssembler, nals: list[bytes]):
        from vt13_video.nal import parse_nal

        access_units = []
        for index, raw in enumerate(nals):
            start_code_len = 4 if raw.startswith(b"\x00\x00\x00\x01") else 3
            nal = parse_nal(raw, start_code_len)
            self.assertIsNotNone(nal)
            access_units.extend(assembler.feed(nal, float(index)))
        access_units.extend(assembler.flush())
        return access_units

    def test_parameter_sets_before_idr_attach_to_idr(self) -> None:
        picture_one = [
            make_nal(35, b"\x30"),
            make_nal(1, b"\x00", first_slice=True),
            make_nal(40, b"\x01"),
        ]
        idr_prefix = [
            make_nal(39, b"\x02"),
            make_nal(32, b"\x03"),
            make_nal(33, b"\x04"),
            make_nal(34, b"\x05"),
            make_nal(20, b"\x00", first_slice=True),
        ]
        assembler = AccessUnitAssembler()
        access_units = self._feed_all(assembler, picture_one + idr_prefix)

        self.assertEqual(len(access_units), 2)
        self.assertFalse(access_units[0].has_irap)
        self.assertFalse(access_units[0].parameter_sets)
        self.assertTrue(access_units[1].has_irap)
        self.assertTrue(access_units[1].has_all_parameter_sets)
        self.assertEqual(
            [nal.nal_type for nal in access_units[1].nals],
            [39, 32, 33, 34, 20],
        )
        self.assertEqual(assembler.discarded_partial_pictures, 0)

    def test_parameters_before_aud_attach_to_following_picture(self) -> None:
        nals = [
            make_nal(35, b"\x30"),
            make_nal(1, b"\x00", first_slice=True),
            make_nal(40, b"\x01"),
            make_nal(32, b"\x02"),
            make_nal(35, b"\x30"),
            make_nal(1, b"\x00", first_slice=True),
        ]
        assembler = AccessUnitAssembler()
        access_units = self._feed_all(assembler, nals)

        self.assertEqual(len(access_units), 2)
        self.assertFalse(access_units[0].parameter_sets)
        self.assertTrue(access_units[1].parameter_sets)
        self.assertEqual([nal.nal_type for nal in access_units[1].nals], [32, 35, 1])

    def test_orphan_non_first_slice_discards_prefix(self) -> None:
        assembler = AccessUnitAssembler()
        prefix = [
            make_nal(32, b"\x01"),
            make_nal(33, b"\x02"),
            make_nal(34, b"\x03"),
        ]
        access_units = self._feed_all(
            assembler,
            prefix + [make_nal(1, b"\x00", first_slice=False)],
        )
        self.assertEqual(access_units, [])
        self.assertEqual(assembler.discarded_partial_pictures, 1)

        access_units = self._feed_all(assembler, [make_nal(1, b"\x00", first_slice=True)])
        self.assertEqual(len(access_units), 1)
        self.assertEqual([nal.nal_type for nal in access_units[0].nals], [1])
        self.assertEqual(access_units[0].parameter_sets, ())

    def test_multiple_slices_stay_in_one_access_unit(self) -> None:
        nals = [
            make_nal(35, b"\x30"),
            make_nal(1, b"\x00", first_slice=True),
            make_nal(1, b"\x01", first_slice=False),
            make_nal(40, b"\x02"),
            make_nal(35, b"\x30"),
            make_nal(1, b"\x00", first_slice=True),
        ]
        assembler = AccessUnitAssembler()
        access_units = self._feed_all(assembler, nals)

        self.assertEqual(len(access_units), 2)
        self.assertEqual([nal.nal_type for nal in access_units[0].nals], [35, 1, 1, 40])
        self.assertEqual(assembler.discarded_partial_pictures, 0)

    def test_parameter_set_types_are_complete(self) -> None:
        self.assertEqual(PARAMETER_SET_TYPES, (32, 33, 34))


class ParameterSetCacheTests(unittest.TestCase):
    def test_write_file_requires_complete_sets_and_writes_annex_b(self) -> None:
        nals = [
            make_nal(32, b"\x01"),
            make_nal(33, b"\x02"),
            make_nal(34, b"\x03"),
        ]
        parsed = scan_nals(b"".join(nals))
        cache = ParameterSetCache()

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "params.h265"
            cache.update(parsed[0])
            with self.assertRaisesRegex(ValueError, "incomplete"):
                cache.write_file(path)
            self.assertFalse(path.exists())

            cache.update_all(parsed[1:])
            output = cache.write_file(path)

            self.assertEqual(output, path)
            self.assertEqual(path.read_bytes(), b"".join(nals))
            self.assertEqual([nal.nal_type for nal in scan_nals(path.read_bytes())], [32, 33, 34])
            self.assertFalse(path.with_name(path.name + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
