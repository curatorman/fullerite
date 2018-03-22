#!/usr/bin/python
# coding=utf-8
###############################################################################
import urllib2

try:
    from xml.etree import ElementTree
except ImportError:
    ElementTree = None

from test import CollectorTestCase
from test import get_collector_config
from test import run_only
from test import unittest
from mock import patch

from diamond.collector import Collector
from kafkastat import KafkaCollector

##########


def run_only_if_ElementTree_is_available(func):
    try:
        from xml.etree import ElementTree
    except ImportError:
        ElementTree = None
    pred = lambda: ElementTree is not None
    return run_only(func, pred)


class TestKafkaCollector(CollectorTestCase):
    def setUp(self):
        config = get_collector_config('KafkaCollector', {
            'interval': 10
        })

        self.collector = KafkaCollector(config, None)

    def _get_xml_fixture(self, name):
        fixture = self.getFixture(name)

        return ElementTree.fromstring(fixture.getvalue())

    def test_import(self):
        self.assertTrue(KafkaCollector)

    def _verify_calls(self, actual, expected):
        assert len(actual) == len(expected)
        for call in actual:
            curr = (call[0][0].split('.')[-1], call[0][1])
            assert curr in expected
            expected.remove(curr)

    @run_only_if_ElementTree_is_available
    @patch('urllib2.urlopen')
    def test_get(self, urlopen_mock):
        urlopen_mock.return_value = self.getFixture('empty.xml')

        result = self.collector._get('/path')
        result_string = ElementTree.tostring(result)

        self.assertEqual(result_string, '<Server />')

    @run_only_if_ElementTree_is_available
    @patch('urllib2.urlopen')
    def test_get_httperror(self, urlopen_mock):
        urlopen_mock.side_effect = urllib2.URLError('BOOM')

        result = self.collector._get('/path')

        self.assertFalse(result)

    @run_only_if_ElementTree_is_available
    @patch('urllib2.urlopen')
    def test_get_bad_xml(self, urlopen_mock):
        urlopen_mock.return_value = self.getFixture('bad.xml')

        result = self.collector._get('/path')

        self.assertFalse(result)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_get_mbeans(self, get_mock):
        get_mock.return_value = self._get_xml_fixture('serverbydomain.xml')

        expected_names = set([
            'kafka:type=kafka.BrokerAllTopicStat',
            'kafka:type=kafka.BrokerTopicStat.mytopic',
            'kafka:type=kafka.LogFlushStats',
            'kafka:type=kafka.SocketServerStats',
            'kafka:type=kafka.logs.mytopic-0',
            'kafka:type=kafka.logs.mytopic-1',
            'kafka:type=kafka.Log4jController',
        ])

        found_beans = self.collector.get_mbeans('*')

        self.assertEqual(found_beans, expected_names)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_get_mbeans_get_fail(self, get_mock):
        get_mock.return_value = None

        found_beans = self.collector.get_mbeans('*')

        self.assertEqual(found_beans, None)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_query_mbean(self, get_mock):
        get_mock.return_value = self._get_xml_fixture('mbean.xml')

        expected_metrics = {
            'kafka.logs.mytopic-1.CurrentOffset': long('213500615'),
            'kafka.logs.mytopic-1.NumAppendedMessages': long('224634137'),
            'kafka.logs.mytopic-1.NumberOfSegments': int('94'),
            'kafka.logs.mytopic-1.Size': long('50143615339'),
        }

        metrics = self.collector.query_mbean('kafka:type=kafka.logs.mytopic-1')

        self.assertEqual(metrics, expected_metrics)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_query_mbean_with_prefix(self, get_mock):
        get_mock.return_value = self._get_xml_fixture('mbean.xml')

        expected_metrics = {
            'some.prefix.CurrentOffset': long('213500615'),
            'some.prefix.NumAppendedMessages': long('224634137'),
            'some.prefix.NumberOfSegments': int('94'),
            'some.prefix.Size': long('50143615339'),
        }

        metrics = self.collector.query_mbean('kafka:type=kafka.logs.mytopic-0',
                                             'some.prefix')

        self.assertEqual(metrics, expected_metrics)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_query_mbean_fail(self, get_mock):
        get_mock.return_value = None

        metrics = self.collector.query_mbean('kafka:type=kafka.logs.mytopic-0')

        self.assertEqual(metrics, None)

    @run_only_if_ElementTree_is_available
    @patch('urllib2.urlopen')
    @patch.object(Collector, 'publish')
    def test(self, publish_mock, urlopen_mock):
        urlopen_mock.side_effect = [
            self.getFixture('serverbydomain_logs_only.xml'),
            self.getFixture('serverbydomain_gc.xml'),
            self.getFixture('serverbydomain_threading.xml'),
            self.getFixture('gc_scavenge.xml'),
            self.getFixture('gc_marksweep.xml'),
            self.getFixture('mbean.xml'),
            self.getFixture('threading.xml'),
        ]
        self.collector.collect()

        # The metrics emitted are slightly inconsistent, but this ensures
        # the latter half are correct.
        expected_metrics = [
            ('CurrentOffset', 213500615L),
            ('NumAppendedMessages', 224634137L),
            ('NumberOfSegments', 94),
            ('Size', 50143615339L),
            ('CurrentThreadCpuTime', 0L),
            ('CurrentThreadUserTime', 0L),
            ('DaemonThreadCount', 58),
            ('PeakThreadCount', 90),
            ('ThreadCount', 89),
            ('TotalStartedThreadCount', 228L),
            ('CollectionCount', 2L),
            ('CollectionTime', 112293L),
            ('CollectionTime', 160L),
            ('CollectionCount', 37577L),
        ]
        calls = publish_mock.call_args_list
        self._verify_calls(calls, expected_metrics)

###############################################################################
if __name__ == "__main__":
    unittest.main()
