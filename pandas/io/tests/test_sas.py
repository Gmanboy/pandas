import pandas as pd
import pandas.util.testing as tm
from pandas import compat
from pandas.io.sas import XportReader, read_sas
import os

# CSV versions of test XPT files were obtained using the R foreign library

class TestXport(tm.TestCase):

    def setUp(self):
        self.dirpath = tm.get_data_path()
        self.file01 = os.path.join(self.dirpath, "DEMO_G.XPT")
        self.file02 = os.path.join(self.dirpath, "SSHSV1_A.XPT")
        self.file03 = os.path.join(self.dirpath, "DRXFCD_G.XPT")


    def test1(self):
        # Tests with DEMO_G.XPT (all numeric file)

        # Compare to this
        data_csv = pd.read_csv(self.file01.replace(".XPT", ".csv"))

        # Read full file
        data = XportReader(self.file01).read()
        tm.assert_frame_equal(data, data_csv, check_dtype=False)

        # Test incremental read with `read` method.
        reader = XportReader(self.file01)
        data = reader.read(10)
        tm.assert_frame_equal(data, data_csv.iloc[0:10, :], check_dtype=False)

        # Test incremental read with `get_chunk` method.
        reader = XportReader(self.file01, chunksize=10)
        data = reader.get_chunk()
        tm.assert_frame_equal(data, data_csv.iloc[0:10, :], check_dtype=False)

        # Read full file with `read_sas` method
        data = read_sas(self.file01)
        tm.assert_frame_equal(data, data_csv, check_dtype=False)


    def test1_index(self):
        # Tests with DEMO_G.XPT using index (all numeric file)

        # Compare to this
        data_csv = pd.read_csv(self.file01.replace(".XPT", ".csv"))
        data_csv = data_csv.set_index("SEQN")

        # Read full file
        data = XportReader(self.file01, index="SEQN").read()
        tm.assert_frame_equal(data, data_csv, check_dtype=False)

        # Test incremental read with `read` method.
        reader = XportReader(self.file01, index="SEQN")
        data = reader.read(10)
        tm.assert_frame_equal(data, data_csv.iloc[0:10, :], check_dtype=False)

        # Test incremental read with `get_chunk` method.
        reader = XportReader(self.file01, index="SEQN", chunksize=10)
        data = reader.get_chunk()
        tm.assert_frame_equal(data, data_csv.iloc[0:10, :], check_dtype=False)


    def test1_incremental(self):
        # Test with DEMO_G.XPT, reading full file incrementally

        data_csv = pd.read_csv(self.file01.replace(".XPT", ".csv"))
        data_csv = data_csv.set_index("SEQN")

        reader = XportReader(self.file01, index="SEQN", chunksize=1000)

        all_data = [x for x in reader]
        data = pd.concat(all_data, axis=0)

        tm.assert_frame_equal(data, data_csv, check_dtype=False)


    def test2(self):
        # Test with SSHSV1_A.XPT

        # Compare to this
        data_csv = pd.read_csv(self.file02.replace(".XPT", ".csv"))

        data = XportReader(self.file02).read()
        tm.assert_frame_equal(data, data_csv, check_dtype=False)


    def test3(self):
        # Test with DRXFCD_G.XPT (contains text and numeric variables)

        # Compare to this
        data_csv = pd.read_csv(self.file03.replace(".XPT", ".csv"))

        data = XportReader(self.file03).read()
        tm.assert_frame_equal(data, data_csv, check_dtype=False)

        data = read_sas(self.file03)
        tm.assert_frame_equal(data, data_csv, check_dtype=False)
