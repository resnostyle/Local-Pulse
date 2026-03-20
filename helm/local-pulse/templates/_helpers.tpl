{{/*
Expand the name of the chart.
*/}}
{{- define "local-pulse.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "local-pulse.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "local-pulse.labels" -}}
helm.sh/chart: {{ include "local-pulse.name" . }}
app.kubernetes.io/name: {{ include "local-pulse.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | default .Chart.Version | quote }}
{{- end }}

{{/*
MySQL host (external)
*/}}
{{- define "local-pulse.mysqlHost" -}}
{{- required "mysql.host is required" .Values.mysql.host }}
{{- end }}

{{/*
MySQL port
*/}}
{{- define "local-pulse.mysqlPort" -}}
{{- .Values.mysql.port | default "3306" }}
{{- end }}

{{/*
Redis service name (chart-managed, in-cluster)
*/}}
{{- define "local-pulse.redisHost" -}}
{{- printf "%s-redis" (include "local-pulse.fullname" .) }}
{{- end }}

{{/*
Celery broker URL (redis://host:6379/0)
*/}}
{{- define "local-pulse.redisUrl" -}}
{{- printf "redis://%s:6379/0" (include "local-pulse.redisHost" .) }}
{{- end }}

{{/*
Celery result backend URL (redis://host:6379/1)
*/}}
{{- define "local-pulse.redisResultUrl" -}}
{{- printf "redis://%s:6379/1" (include "local-pulse.redisHost" .) }}
{{- end }}
