"""
Copyright 2016-2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at

http://aws.amazon.com/apache2.0/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
"""

from cidr_findr import CidrFindr, CidrFindrException
from cidr_findr.lambda_utils import parse_size, sizes_valid
import unittest

class CidrFindrTestCase(unittest.TestCase):
    """
    Test the find_next_subnet function
    """

    def __get_cidrs(self, vpc=None, vpcs=[], subnets=[], requests=[]):
        self.findr = CidrFindr(network=vpc, networks=vpcs, subnets=subnets)

        return [
            self.findr.next_subnet(request)
            for request in requests
        ]

    def test_no_subnets(self):
        """
        No existing subnets
        """

        actual = self.__get_cidrs(
            "10.0.0.0/16",
            requests=[24]
        )

        expected = ["10.0.0.0/24"]

        self.assertEqual(actual, expected)

    def test_one_subnet(self):
        """
        One subnet at the beginning
        """

        actual = self.__get_cidrs(
            "10.0.0.0/16",
            subnets=["10.0.0.0/24"],
            requests=[24],
        )

        expected = ["10.0.1.0/24"]

        self.assertEqual(actual, expected)

    def test_two_adjacent_at_start(self):
        """
        Two adjacent subnets at the beginning
        """

        actual = self.__get_cidrs(
            vpc="10.0.0.0/16",
            subnets=["10.0.0.0/24", "10.0.1.0/24"],
            requests=[24],
        )

        expected = ["10.0.2.0/24"]

        self.assertEqual(actual, expected)

    def test_two_adjacent_at_start_2(self):
        """
        Two adjacent subnets at the beginning, looking for two more
        """

        actual = self.__get_cidrs(
            vpc="10.0.0.0/16",
            subnets=["10.0.0.0/24", "10.0.1.0/24"],
            requests=[24, 24],
        )

        expected = ["10.0.2.0/24", "10.0.3.0/24"]

        self.assertEqual(actual, expected)

    def test_different_sizes(self):
        """
        One subnet at the beginning, looking for two different sized subnet
        The second subnet can squeeze in beside the existing one :)
        """

        actual = self.__get_cidrs(
            vpc="10.0.0.0/16",
            subnets=["10.0.0.0/25"],
            requests=[24, 25],
        )

        expected = ["10.0.1.0/24", "10.0.0.128/25"]

        self.assertEqual(actual, expected)

    def test_unordered_subnets(self):
        """
        Existing subnets not supplied in size order
        """

        actual = self.__get_cidrs(
            vpc="172.31.0.0/16",
            subnets=["172.31.48.0/20", "172.31.0.0/20", "172.31.16.0/20", "172.31.32.0/20"],
            requests=[24],
        )

        expected = ["172.31.64.0/24"]

        self.assertEqual(actual, expected)

    def test_middle_gap(self):
        """
        A subnet should fit in the gap
        """

        actual = self.__get_cidrs(
            vpc="192.168.1.0/24",
            subnets=["192.168.1.0/26", "192.168.1.128/25"],
            requests=[26],
        )

        expected = ["192.168.1.64/26"]

        self.assertEqual(actual, expected)

    def test_network_too_small(self):
        """
        Request won't fit in the network
        """

        findr = CidrFindr(network="10.0.0.0/25")

        with self.assertRaisesRegex(CidrFindrException, "Not enough space for the requested CIDR blocks"):
            findr.next_subnet(24)

    def test_network_full(self):
        """
        Existing subnet fills entire network
        """

        findr = CidrFindr(network="10.0.0.0/24", subnets=["10.0.0.0/24"])

        with self.assertRaisesRegex(CidrFindrException, "Not enough space for the requested CIDR blocks"):
            findr.next_subnet(24)

    def test_insufficient_space(self):
        """
        Subnet in the middle but not enough space either side
        """

        findr = CidrFindr(network="10.0.0.0/24", subnets=["10.0.0.64/25"])

        with self.assertRaisesRegex(CidrFindrException, "Not enough space for the requested CIDR blocks"):
            findr.next_subnet(25)

    def test_gap_at_start(self):
        """
        Big enough gap at the beginning, filled after
        """

        actual = self.__get_cidrs(
            vpc="10.0.0.0/24",
            subnets=["10.0.0.128/25"],
            requests=[25],
        )

        expected = ["10.0.0.0/25"]

        self.assertEqual(actual, expected)

    def test_complete_overlap(self):
        """
        Requirement would overlap an existing subnet completely
        """

        actual = self.__get_cidrs(
            vpc="10.0.0.0/16",
            subnets=["10.0.0.64/26"],
            requests=[25],
        )

        expected = ["10.0.0.128/25"]

        self.assertEqual(actual, expected)

    def test_strings_in_input(self):
        """
        Strings are converted correctly into numbers
        """

        actual = self.__get_cidrs(
            vpc="10.0.0.0/16",
            requests=[24],
        )

        expected = ["10.0.0.0/24"]

        self.assertEqual(actual, expected)

    def test_multiple_vpcs(self):
        """
        Find space across multiple VPCs
        """

        actual = self.__get_cidrs(
            vpcs=["10.0.0.0/24", "10.0.1.0/24"],
            subnets=["10.0.0.0/25", "10.0.1.0/25"],
            requests=[25, 25],
        )

        expected = ["10.0.0.128/25", "10.0.1.128/25"]

        self.assertEqual(actual, expected)

    def test_netmask(self):
        """
        Test that the netmask is respected.
        e.g. With two /24s, a /22 can't start at 10.0.2.0
        """

        actual = self.__get_cidrs(
            vpc="10.0.0.0/16",
            subnets=["10.0.0.0/24", "10.0.1.0/24"],
            requests=[22],
        )

        expected = ["10.0.4.0/22"]

        self.assertEqual(actual, expected)

    def test_subnet_is_smaller(self):
        """
        Test that we can't put a /16 subnet into a /16 network
        """

        with self.assertRaisesRegex(CidrFindrException, "Not enough space for the requested CIDR blocks"):
            self.__get_cidrs(
                vpc="10.0.0.0/16",
                requests=[16],
            )
