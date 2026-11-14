import contextlib
import io
import logging
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

try:
    import pypushdeer
except ImportError:
    sys.modules['pypushdeer']=types.SimpleNamespace(PushDeer=MagicMock())
import checkin as app
app.logger.handlers=[]
app.logger.addHandler(logging.NullHandler())

class DiagnosticsTests(unittest.TestCase):
    def test_verification_is_action_required_not_success_or_cookie_expiry(self):
        api=app.API('glados.cloud',1)
        with patch.object(api,'_checkin_attempt',return_value={'code':5,'message':'Cloudflare verification failed. Nothing was recorded — please retry.'}) as send:
            result=api.checkin('private-cookie')
        self.assertEqual(result['code'],app.CheckinStatus.FAILURE)
        self.assertIn('需要官网验证',result['status'])
        self.assertNotIn('过期',result['status'])
        send.assert_called_once()

    def test_auth_failure_and_success_are_distinct(self):
        api=app.API('railgun.info',1)
        result=api._parse_checkin({'code':-2,'message':'No permission'})
        self.assertEqual(result['status'],'该域名未接受登录凭证')
        self.assertEqual(api._parse_checkin({'code':0,'points':7})['code'],app.CheckinStatus.SUCCESS)
        self.assertEqual(api._parse_checkin({'code':1})['code'],app.CheckinStatus.REPEAT)

    def checker(self):
        checker=app.Checker(types.SimpleNamespace(verbose=False,cookies_list=['PRIVATE-COOKIE-MUST-NOT-LEAK'],push_key=''))
        checker.results=[app.CheckinResult(1,'glados.cloud',status='需要官网验证（本次未签到）'),app.CheckinResult(1,'railgun.info',status='该域名未接受登录凭证')]
        return checker

    def test_non_verbose_results_identify_each_domain(self):
        _,content,log=self.checker().format_results()
        self.assertIn('glados.cloud',content)
        self.assertIn('railgun.info',log)
        self.assertIn('需要官网验证',log)

    def test_actions_summary_has_guidance_without_private_credentials(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'summary.md'
            with patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(path)}):self.checker().write_actions_summary()
            text=path.read_text(encoding='utf-8')
            self.assertIn('本次没有签到',text)
            self.assertIn('https://glados.cloud/',text)
            self.assertNotIn('PRIVATE-COOKIE',text)

    def test_unavailable_summary_file_does_not_mask_result(self):
        with patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':'unused'}),patch('builtins.open',side_effect=OSError('disk unavailable')):
            self.checker().write_actions_summary()

    def run_main(self,results,cookies=None):
        config=types.SimpleNamespace(cookies_list=cookies or ['cookie'],push_key='')
        checker=self.checker()
        checker.results=results
        with patch.object(app,'Config',return_value=config),patch.object(app,'Checker',return_value=checker),patch.object(checker,'checkin_all'),patch.object(checker,'write_actions_summary'),patch.object(app.PushService,'send',return_value=False):
            return app.main()

    def test_all_domains_failed_still_exit_nonzero(self):
        self.assertEqual(self.run_main(self.checker().results),1)

    def test_one_domain_success_or_repeat_still_satisfies_the_cookie(self):
        for code in [app.CheckinStatus.SUCCESS,app.CheckinStatus.REPEAT]:
            self.assertEqual(self.run_main([app.CheckinResult(1,'glados.cloud',code=code),app.CheckinResult(1,'railgun.info')]),0)

    def test_one_failed_account_cannot_be_hidden_by_another_success(self):
        self.assertEqual(self.run_main([app.CheckinResult(1,'glados.cloud',code=app.CheckinStatus.SUCCESS),app.CheckinResult(2,'glados.cloud')],['one','two']),1)

if __name__=='__main__':unittest.main()
