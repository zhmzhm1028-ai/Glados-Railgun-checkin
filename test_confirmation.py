from datetime import datetime,timezone,timedelta
import sys
import types
import unittest
from unittest.mock import MagicMock,patch
try:import pypushdeer
except ImportError:sys.modules['pypushdeer']=types.SimpleNamespace(PushDeer=MagicMock())
import checkin as app

def response(data):
    r=MagicMock();r.json.return_value=data;r.ok=True
    return r

class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.api=app.API('glados.cloud',1)
        self.clock=patch.object(app,'datetime');self.now=self.clock.start()
        self.now.now.return_value=datetime(2026,11,14,10,0,tzinfo=timezone(timedelta(hours=8)))
    def tearDown(self):self.clock.stop();self.api.close()

    def run_checkin(self,trend):
        with patch.object(self.api,'_make_request',side_effect=[response({'code':0,'nonce':'n','turnstile':{'sitekey':'public'}}),response(trend)]) as send:
            result=self.api.checkin('not-a-real-cookie')
        self.assertEqual([c.args[1] for c in send.call_args_list],['GET','GET'])
        return result

    def test_positive_today_record_confirms_attended_checkin_without_post(self):
        r=self.run_checkin({'code':0,'data':{'days':[{'date':'2026-11-14','checkin':2}]}})
        self.assertEqual(r['code'],app.CheckinStatus.REPEAT);self.assertEqual(r['points'],'0')

    def test_previous_day_cannot_claim_today_was_completed(self):
        r=self.run_checkin({'code':0,'data':{'days':[{'date':'2026-11-13','checkin':20}]}})
        self.assertEqual(r['code'],app.CheckinStatus.FAILURE)

    def test_other_points_and_zero_checkin_are_not_confirmation(self):
        r=self.run_checkin({'code':0,'data':{'days':[{'date':'2026-11-14','checkin':0,'casino':100,'other':100}]}})
        self.assertEqual(r['code'],app.CheckinStatus.FAILURE)

    def test_malformed_or_unauthorized_trend_never_claims_success(self):
        cases=[None,[],{'code':-2},{'code':'0','data':{'days':[]}},{'code':0,'data':[]},{'code':0,'data':{'days':{}}}]
        for data in cases:
            with self.subTest(data=data):self.assertEqual(self.run_checkin(data)['code'],app.CheckinStatus.FAILURE)

    def test_boolean_nonfinite_and_string_checkin_values_are_not_confirmation(self):
        for earned in [True,float('inf'),float('nan'),'2',-1]:
            with self.subTest(earned=earned):
                self.assertEqual(self.run_checkin({'code':0,'data':{'days':[{'date':'2026-11-14','checkin':earned}]}})['code'],app.CheckinStatus.FAILURE)

    def test_unavailable_trend_keeps_verification_required(self):
        with patch.object(self.api,'_make_request',side_effect=[response({'code':0,'nonce':'n','turnstile':{'sitekey':'public'}}),None]) as send:
            r=self.api.checkin('cookie')
        self.assertEqual(r['code'],app.CheckinStatus.FAILURE);self.assertEqual(send.call_count,2)

    def test_confirmation_uses_china_calendar_day(self):
        with patch.object(self.api,'_make_request',return_value=response({'code':0,'data':{'days':[{'date':'2026-11-14','checkin':2}]}})):
            self.assertTrue(self.api._confirmed_today('cookie',None))
        self.assertEqual(self.now.now.call_args.args[0].utcoffset(None),timedelta(hours=8))

if __name__=='__main__':unittest.main()
