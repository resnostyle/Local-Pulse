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
{{- end }}

{{/*
MySQL host - internal service or external
*/}}
{{- define "local-pulse.mysqlHost" -}}
{{- if .Values.mysql.enabled }}
{{- printf "%s-mysql" (include "local-pulse.fullname" .) }}
{{- else }}
{{- .Values.externalMysql.host }}
{{- end }}
{{- end }}

{{/*
MySQL port
*/}}
{{- define "local-pulse.mysqlPort" -}}
{{- if .Values.mysql.enabled }}
{{- "3306" }}
{{- else }}
{{- .Values.externalMysql.port | default "3306" }}
{{- end }}
{{- end }}
