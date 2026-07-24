{{- /* ────────────────────────────────────────────────
  Forge Helm Helpers
  ──────────────────────────────────────────────── */}}

{{- /*
  Build a full image reference.
  Usage: {{ include "forge.image" (dict "root" . "imageSpec" .Values.redis.image) }}
*/}}
{{- define "forge.image" -}}
{{- $registry := .root.Values.global.imageRegistry | default "" -}}
{{- $repo := .imageSpec.repository -}}
{{- $tag := .imageSpec.tag | default "latest" -}}
{{- if $registry -}}
  {{- printf "%s/%s:%s" $registry $repo $tag -}}
{{- else -}}
  {{- printf "%s:%s" $repo $tag -}}
{{- end -}}
{{- end -}}

{{- /* Standard labels */}}
{{- define "forge.labels" -}}
helm.sh/chart: "{{ .Chart.Name }}-{{ .Chart.Version }}"
app.kubernetes.io/name: "{{ .Chart.Name }}"
app.kubernetes.io/instance: "{{ .Release.Name }}"
app.kubernetes.io/managed-by: "{{ .Release.Service }}"
app.kubernetes.io/version: "{{ .Chart.AppVersion }}"
{{- end -}}

{{- /* Selector labels */}}
{{- define "forge.selectorLabels" -}}
app.kubernetes.io/name: "{{ .Chart.Name }}"
app.kubernetes.io/instance: "{{ .Release.Name }}"
{{- end -}}

{{- /* Component label */}}
{{- define "forge.component" -}}
{{- printf "app.kubernetes.io/component: %s" .component -}}
{{- end -}}

{{- /* ServiceAccount name */}}
{{- define "forge.serviceAccountName" -}}
{{- default "forge" .Values.serviceAccount.name -}}
{{- end -}}
