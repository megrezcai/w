// Attach to a Unity GameObject. Start CaseForge first, then copy its local API token.
using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

public class CaseForgeClient : MonoBehaviour
{
    public string baseUrl = "http://127.0.0.1:8765";
    public string localToken = "";
    private string sessionId;
    [Serializable] class SessionRequest {
        public string chapter_id = "rain_manor";
        public string character_id = "butler";
        public string[] inventory = { "camera" };
        public string[] available_offers = { "protect_family", "record_cooperation" };
    }
    [Serializable] class SessionResponse { public string session_id; }
    [Serializable] class TurnRequest { public string text; public string[] evidence_ids; public string[] offer_ids; }
    [Serializable] class TurnResponse { public string reply; public string warning; }
    IEnumerator Start() {
        yield return Post("/api/sessions", JsonUtility.ToJson(new SessionRequest()), body => {
            sessionId = JsonUtility.FromJson<SessionResponse>(body).session_id;
            Debug.Log("CaseForge session ready: " + sessionId);
        });
    }
    public void Ask(string playerText, string[] presentedEvidence, string[] confirmedOffers) {
        if (String.IsNullOrEmpty(sessionId)) { Debug.LogWarning("Session not ready"); return; }
        StartCoroutine(Post("/api/sessions/" + sessionId + "/turn", JsonUtility.ToJson(new TurnRequest {
            text = playerText, evidence_ids = presentedEvidence ?? new string[0], offer_ids = confirmedOffers ?? new string[0]
        }), body => {
            var reply = JsonUtility.FromJson<TurnResponse>(body);
            Debug.Log(reply.reply); // Replace this with your dialogue UI and subtitle system.
            if (!String.IsNullOrEmpty(reply.warning)) Debug.LogWarning(reply.warning);
        }));
    }
    IEnumerator Post(string path, string json, Action<string> completed) {
        using (var request = new UnityWebRequest(baseUrl + path, "POST")) {
            request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("X-Caseforge-Token", localToken);
            request.timeout = 240;
            yield return request.SendWebRequest();
            if (request.result != UnityWebRequest.Result.Success) Debug.LogError(request.error + " " + request.downloadHandler.text);
            else completed(request.downloadHandler.text);
        }
    }
}
