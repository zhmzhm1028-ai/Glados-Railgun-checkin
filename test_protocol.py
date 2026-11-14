import hashlib
from pathlib import Path
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

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.api=app.API('glados.cloud',1)
        self.sleep=patch.object(app.time,'sleep');self.wait=self.sleep.start()
        self.clock=patch.object(app.time,'monotonic',return_value=100);self.clock.start()
    def tearDown(self):self.sleep.stop();self.clock.stop();self.api.close()
    def run_checkin(self,challenge,result=None):
        self.calls=patch.object(self.api,'_make_request',side_effect=[response(challenge),response(result or {'code':0,'points':2})])
        with self.calls as send:
            result=self.api.checkin('not-a-real-cookie')
            return result,send.call_args_list

    def test_new_protocol_uses_fresh_nonce_correct_hash_delay_and_json(self):
        result,calls=self.run_checkin({'code':0,'nonce':'nonce-a','ttl':300000})
        self.assertEqual(result['code'],app.CheckinStatus.SUCCESS)
        self.assertEqual(calls[0].args[1],'GET');self.assertEqual(calls[1].args[1],'POST')
        payload=calls[1].args[2]
        self.assertEqual(payload,{'token':'glados.cloud','nonce':'nonce-a','proof':hashlib.sha256(b'nonce-a.glados-observe-v1').hexdigest(),'tsState':'off'})
        self.assertTrue(calls[1].kwargs['json_body']);self.wait.assert_called_once_with(2.5)

    def test_required_human_verification_never_posts_or_forges_a_token(self):
        result,calls=self.run_checkin({'code':0,'nonce':'n','ttl':300000,'turnstile':{'sitekey':'public-site-key'}})
        self.assertEqual(result['code'],app.CheckinStatus.FAILURE);self.assertIn('官网验证',result['status'])
        self.assertEqual(len(calls),1);self.wait.assert_not_called()

    def test_missing_nonce_or_bad_ttl_never_falls_back_to_legacy_post(self):
        for data in [{'code':0},{'code':0,'nonce':4},{'code':0,'nonce':'n','ttl':True},{'code':0,'nonce':'n','ttl':0},{'code':0,'nonce':'n','ttl':float('nan')}]:
            with self.subTest(data=data):
                result,calls=self.run_checkin(data)
                self.assertEqual(result['code'],app.CheckinStatus.FAILURE);self.assertEqual(len(calls),1)

    def test_challenge_error_or_non_object_does_not_post(self):
        for data in [[],None,{'code':'0'},{'code':-2,'message':'No permission'}]:
            with self.subTest(data=data):
                result,calls=self.run_checkin(data);self.assertEqual(result['code'],app.CheckinStatus.FAILURE);self.assertEqual(len(calls),1)

    def test_unavailable_or_non_json_challenge_does_not_post(self):
        broken=response({});broken.json.side_effect=ValueError('bad json')
        for first in [None,broken]:
            with patch.object(self.api,'_make_request',return_value=first) as send:
                self.assertEqual(self.api.checkin('cookie')['code'],app.CheckinStatus.FAILURE);send.assert_called_once()

    def test_expired_nonce_is_not_submitted(self):
        with patch.object(app.time,'monotonic',side_effect=[100,401]):
            result,calls=self.run_checkin({'code':0,'nonce':'expired','ttl':300000})
        self.assertEqual(result['code'],app.CheckinStatus.FAILURE);self.assertEqual(len(calls),1)

    def test_too_short_lifetime_never_waits_or_posts(self):
        result,calls=self.run_checkin({'code':0,'nonce':'short','ttl':2000})
        self.assertEqual(result['code'],app.CheckinStatus.FAILURE);self.assertEqual(len(calls),1);self.wait.assert_not_called()

    def test_new_repeat_flag_and_legacy_repeat_are_not_new_points(self):
        for data in [{'code':0,'repeated':True,'points':99},{'code':1,'points':99}]:
            result=self.api._parse_checkin(data);self.assertEqual(result['code'],app.CheckinStatus.REPEAT);self.assertEqual(result['points'],'0')

    def test_invalid_success_codes_and_response_shapes_are_not_success(self):
        for data in [[],{'code':False},{'code':'0'},{'code':None}]:
            self.assertEqual(self.api._parse_checkin(data)['code'],app.CheckinStatus.FAILURE)

    def test_device_retry_fetches_a_new_challenge(self):
        responses=[response({'code':0,'nonce':'first'}),response({'code':4,'reason':'device-mismatch','loginDevice':'iPhone'}),response({'code':0,'nonce':'second'}),response({'code':0,'repeated':True})]
        with patch.object(self.api,'_make_request',side_effect=responses) as send:
            result=self.api.checkin('cookie')
        self.assertEqual(result['code'],app.CheckinStatus.REPEAT)
        self.assertEqual([c.args[1] for c in send.call_args_list],['GET','POST','GET','POST'])
        self.assertEqual(send.call_args_list[3].args[2]['nonce'],'second')
        self.assertEqual(send.call_args_list[2].kwargs['user_agent'],app.PLATFORM_UA['iPhone'])

    def test_post_transport_uses_json_and_does_not_automatically_replay_nonce(self):
        with patch.object(self.api.session,'post',return_value=response({})) as post:
            self.api._make_request('https://glados.cloud/api/user/checkin','POST',{'nonce':'n'},'cookie',json_body=True)
        self.assertIn('json',post.call_args.kwargs);self.assertNotIn('data',post.call_args.kwargs)
        self.assertNotIn('POST',self.api.session.get_adapter('https://').max_retries.allowed_methods)

    def test_form_posts_for_existing_exchange_remain_supported(self):
        with patch.object(self.api.session,'post',return_value=response({})) as post:
            self.api._make_request('https://glados.cloud/api/user/exchange','POST',{'plan':'unchanged'},'cookie')
        self.assertIn('data',post.call_args.kwargs);self.assertNotIn('json',post.call_args.kwargs)

if __name__=='__main__':unittest.main()
